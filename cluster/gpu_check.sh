#!/usr/bin/env bash
# What GPU is this, and can the installed torch actually use it?
#
#   ./cluster/gpu_check.sh
#
# Run this on a machine before queueing work to it. It answers the question
# torch.cuda.is_available() does not: whether the wheel contains kernels for
# this device's compute capability.

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

load_config
load_modules

echo
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=index,name,compute_cap,memory.total,driver_version \
             --format=csv 2>/dev/null || nvidia-smi | head -12
else
  echo "no nvidia-smi on $HOST"
fi

echo
if [[ ! -f "$(VENV_DIR)/bin/activate" ]]; then
  echo "No venv yet at $(VENV_DIR) - run ./cluster/setup.sh first."
  exit 0
fi
activate_venv

python - <<'PY'
import sys
import torch

print(f"\ntorch          {torch.__version__}")
print(f"cuda available {torch.cuda.is_available()}")
if not torch.cuda.is_available():
    print("\nNo CUDA device visible to torch on this host.")
    sys.exit(1)

print(f"built for      {' '.join(torch.cuda.get_arch_list())}")
print()

bad = 0
for i in range(torch.cuda.device_count()):
    p = torch.cuda.get_device_properties(i)
    cap = torch.cuda.get_device_capability(i)
    sm = f"sm_{cap[0]}{cap[1]}"
    line = f"[{i}] {p.name:<28} {sm:<8} {p.total_memory / 1024**3:5.1f} GiB"
    try:
        x = torch.randn(64, 64, device=f"cuda:{i}")
        float((x @ x).sum().item())
        print(f"{line}  USABLE")
    except Exception as e:
        bad += 1
        print(f"{line}  UNUSABLE - {type(e).__name__}")
        print(f"     {str(e).splitlines()[0]}")
        if cap[0] >= 12:
            print(f"     Device is newer than this build. Try TORCH_CUDA=cu128.")
        else:
            print(f"     Device is older than this build. Try TORCH_CUDA=cu118.")
            print(f"     If cu118 also fails, this GPU predates the torch>=2.6")
            print(f"     transformers needs, and this host cannot run the jobs.")

if bad:
    print(f"\nSet TORCH_CUDA in cluster/config/{__import__('socket').gethostname().split('.')[0]}.env")
    print("and re-run ./cluster/setup.sh, then ./cluster/gpu_check.sh again.")
    sys.exit(1)

print("\nAll GPUs on this host can run the jobs.")
PY
