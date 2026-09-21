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
if [[ "$TORCH_CUDA" == "cpu" ]]; then
  echo "Installing torch (CPU build)"
  python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
else
  echo "Installing torch (CUDA $TORCH_CUDA)"
  python -m pip install torch --index-url "https://download.pytorch.org/whl/$TORCH_CUDA"
fi

echo "Installing pipeline requirements"
python -m pip install -r "$REPO_DIR/dataset/categorization/requirements.txt"
python -m pip install -r "$REPO_DIR/dataset/finetune/requirements.txt"

echo
echo "--- verification ---"
python - <<'PY'
import torch, transformers, sys
print(f"torch        {torch.__version__}")
print(f"transformers {transformers.__version__}")
print(f"cuda available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        p = torch.cuda.get_device_properties(i)
        print(f"  [{i}] {p.name}, {p.total_memory / 1024**3:.1f} GiB")
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
