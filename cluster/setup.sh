#!/usr/bin/env bash
# One-time environment build on a cluster host.
#
#   CLUSTER=labic ./cluster/setup.sh
#   CLUSTER=cdi   ./cluster/setup.sh
#
# Idempotent: re-run it to pick up dependency changes.

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

load_config
load_modules
export_caches
report_gpu

mkdir -p "$WORKDIR"
VENV="$(VENV_DIR)"

if [[ ! -d "$VENV" ]]; then
  echo "Creating venv at $VENV"
  "$PYTHON_BIN" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
echo "Python:   $(python -V 2>&1)"

python -m pip install --upgrade pip wheel >/dev/null

# torch first, from the index matching the node's CUDA. Installing it via the
# requirements files instead would pull the default PyPI wheel, which on Linux
# is the CUDA build for whatever CUDA that release defaults to - not
# necessarily the one this driver supports.
# torch>=2.6 is a hard requirement, not a preference. transformers refuses to
# torch.load a .bin checkpoint on anything older (CVE-2025-32434), and
# microsoft/unixcoder-base ships only pytorch_model.bin - no safetensors - so
# every run would die at from_pretrained.
#
# This interacts with TORCH_CUDA in a way that is easy to miss: the cu121 index
# stops at torch 2.5.1, so asking for cu121 silently caps you below the
# requirement. Pinning the version here makes pip fail at install time, with a
# resolver error naming the index, instead of at model load an hour later.
TORCH_SPEC="torch>=2.6"

# pip resolves "torch>=2.6" against the version alone and ignores the build
# variant, so an installed 2.14.0+cu126 satisfies it and pip does nothing -
# even when the config now asks for cu130. Changing TORCH_CUDA would then have
# no effect at all, which is exactly what happened on the Blackwell host.
# Compare the installed local tag with the wanted one and force the reinstall
# when they differ.
HAVE="$(python - <<'PY' 2>/dev/null || echo none
try:
    import torch
    v = torch.__version__
    print(v.split("+", 1)[1] if "+" in v else "cpu")
except Exception:
    print("none")
PY
)"
WANT="$TORCH_CUDA"
FORCE=()
if [[ "$HAVE" == "none" ]]; then
  echo "torch:    not installed yet"
elif [[ "$HAVE" == "$WANT" ]]; then
  echo "torch:    already $HAVE, leaving it alone"
else
  echo "torch:    installed build is $HAVE but this host wants $WANT - reinstalling"
  FORCE=(--force-reinstall --no-cache-dir)
fi

if [[ "$TORCH_CUDA" == "cpu" ]]; then
  echo "Installing $TORCH_SPEC (CPU build)"
  python -m pip install ${FORCE[@]+"${FORCE[@]}"} "$TORCH_SPEC" \
    --index-url https://download.pytorch.org/whl/cpu
else
  echo "Installing $TORCH_SPEC (CUDA $TORCH_CUDA)"
  if ! python -m pip install ${FORCE[@]+"${FORCE[@]}"} "$TORCH_SPEC" \
       --index-url "https://download.pytorch.org/whl/$TORCH_CUDA"; then
    cat >&2 <<EOF

The $TORCH_CUDA index cannot provide torch>=2.6.

Highest torch per index, as of writing:
  cu118  2.7.1    pre-Pascal devices
  cu121  2.5.1    <- too old, do not use
  cu124  2.6.0
  cu126  2.14.0   <- default, but sm_50..sm_90 only
  cu128  2.11.0
  cu130  2.14.0   <- CUDA 13, needed for Blackwell sm_120
  cu132  2.14.0

Pick an index that has >=2.6 and that your driver supports, set TORCH_CUDA in
the host config, and re-run. CUDA 12.x drivers are minor-version compatible, so
a 12.x driver generally runs any cu12x build.
EOF
    exit 1
  fi
fi

echo "Installing pipeline requirements"
python -m pip install -r "$REPO_DIR/dataset/categorization/requirements.txt"
python -m pip install -r "$REPO_DIR/dataset/finetune/requirements.txt"

echo
echo "--- verification ---"
TORCH_CUDA="$TORCH_CUDA" python - <<'PY'
import torch, transformers, sys
print(f"torch        {torch.__version__}")
print(f"transformers {transformers.__version__}")

import os
want = os.environ.get("TORCH_CUDA", "")
have = torch.__version__.split("+", 1)[1] if "+" in torch.__version__ else "cpu"
if want and have != want:
    print(f"  ERROR: wanted a {want} build, got {have}.")
    print(f"  pip treats 'torch>=2.6' as satisfied by any build of a new enough")
    print(f"  version, so it will not swap cu126 for cu130 on its own. Try:")
    print(f"    pip install --force-reinstall --no-cache-dir torch=={torch.__version__.split('+')[0]} \\")
    print(f"      --index-url https://download.pytorch.org/whl/{want}")
    sys.exit(1)

major, minor = (int(x) for x in torch.__version__.split(".")[:2])
if (major, minor) < (2, 6):
    print(f"  ERROR: torch {torch.__version__} is too old.")
    print("  transformers will refuse to load microsoft/unixcoder-base, which")
    print("  ships only pytorch_model.bin, because torch.load is unsafe before")
    print("  2.6 (CVE-2025-32434). Set TORCH_CUDA to an index carrying >=2.6")
    print("  (cu124, cu126, cu130, cu132 or cu118 - not cu121) and re-run setup.sh.")
    sys.exit(1)
print(f"cuda available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"built for:      {' '.join(torch.cuda.get_arch_list())}")
    ok = True
    for i in range(torch.cuda.device_count()):
        p = torch.cuda.get_device_properties(i)
        cap = torch.cuda.get_device_capability(i)
        sm = f"sm_{cap[0]}{cap[1]}"
        print(f"  [{i}] {p.name}, {p.total_memory / 1024**3:.1f} GiB, {sm}")

        # torch.cuda.is_available() only says a driver and a device exist. It
        # returns True when the installed wheel has no kernels compiled for
        # this GPU's architecture, and the job then dies hours later with
        # "no kernel image is available for execution on the device". The only
        # honest check is to run something on the device.
        try:
            x = torch.randn(64, 64, device=f"cuda:{i}")
            float((x @ x).sum().item())
            print(f"       matmul OK")
        except Exception as e:
            ok = False
            print(f"       FAILS: {type(e).__name__}: {str(e).splitlines()[0]}")
            print(f"       This wheel has no kernels for {sm}.")
            if cap[0] >= 12:
                print(f"       {p.name} is newer than this build. sm_120 (Blackwell)")
                print(f"       needs a CUDA 13 wheel - TORCH_CUDA=cu130.")
            else:
                print(f"       {p.name} is older than this build - try TORCH_CUDA=cu118,")
                print(f"       and if that still fails the GPU predates the torch>=2.6")
                print(f"       that transformers requires, so this host cannot run the job.")
    if not ok:
        print("\n  Set TORCH_CUDA in cluster/config/$(hostname -s).env and re-run setup.sh.")
        sys.exit(1)
else:
    print("  WARNING: no GPU visible to torch.")
    if "+cpu" in torch.__version__:
        print("  The installed torch is a CPU-only build - set TORCH_CUDA in the")
        print("  host config to match nvidia-smi and re-run setup.sh.")
    else:
        print("  torch has CUDA support but sees no device; check that this is a")
        print("  GPU node and that CUDA_VISIBLE_DEVICES is not empty.")
if transformers.__version__.split(".")[0] not in ("4",):
    print("  WARNING: transformers must be <5 - see categorization/requirements.txt")
    sys.exit(1)
PY

echo
echo "Verifying the dataset artifact"
python "$REPO_DIR/dataset/scripts/smoke_test.py"

echo
echo "Setup complete. Launch jobs with:  CLUSTER=$CLUSTER ./cluster/run.sh <job>"
