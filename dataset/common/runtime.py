"""Device and hyper-parameter selection, shared by every pipeline.

The pipelines used to hardcode `torch.device("cpu")`. On a GPU node that is
silently wrong: the job runs, produces correct results, and takes twenty hours
instead of twenty minutes. `get_device()` picks the accelerator when there is
one and says out loud what it picked.

Batch size and epoch count come from the environment so that a cluster run can
be tuned without editing tracked code - the CPU defaults are small because they
were chosen to fit in a few GB of RAM.

    DEVICE=cuda|cpu|auto   default auto
    BATCH_SIZE=<int>
    EVAL_BATCH_SIZE=<int>
    EPOCHS=<int>
"""

import os

import torch


def _assert_cuda_usable():
    """Run something on the GPU before trusting it.

    torch.cuda.is_available() checks for a driver and a device, not for
    kernels this GPU can execute. A wheel built without support for the
    device's compute capability passes that check and then fails at the first
    forward pass with "no kernel image is available for execution on the
    device" - which on a training job means hours later, on a shared machine,
    with nothing to show. One 64x64 matmul settles it in milliseconds.
    """
    try:
        x = torch.randn(64, 64, device="cuda")
        float((x @ x).sum().item())
    except Exception as e:
        cap = torch.cuda.get_device_capability(0)
        name = torch.cuda.get_device_name(0)
        raise RuntimeError(
            f"CUDA is present but unusable on this host.\n"
            f"  device:    {name} (sm_{cap[0]}{cap[1]})\n"
            f"  torch:     {torch.__version__}\n"
            f"  built for: {' '.join(torch.cuda.get_arch_list())}\n"
            f"  error:     {type(e).__name__}: {str(e).splitlines()[0]}\n"
            f"This wheel has no kernels for this GPU. torch usually prints "
            f"the exact wheel indexes to use just above this, for your torch "
            f"version; follow those. Set TORCH_CUDA in "
            f"cluster/config/<hostname>.env and re-run cluster/setup.sh. "
            f"As a guide: Blackwell (sm_120) needs a CUDA 13 build such as "
            f"cu130, and a pre-Pascal device needs cu118 - but note the index "
            f"also caps the torch version, and this project needs >=2.6."
        ) from e


def get_device(announce=True):
    """Pick the device, honouring a DEVICE override."""
    requested = os.environ.get("DEVICE", "auto").lower()

    if requested == "cpu":
        device = torch.device("cpu")
    elif requested == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError(
                "DEVICE=cuda was requested but torch.cuda.is_available() is "
                "False. Usually this means a CPU-only torch build was "
                f"installed (this one is {torch.__version__}) or the job is not "
                "on a GPU node."
            )
        device = torch.device("cuda")
    elif requested == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        raise ValueError(f"DEVICE must be auto, cuda or cpu; got {requested!r}")

    if device.type == "cuda":
        _assert_cuda_usable()

    if announce:
        if device.type == "cuda":
            name = torch.cuda.get_device_name(0)
            total = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
            cap = torch.cuda.get_device_capability(0)
            print(f"Device: cuda - {name}, {total:.1f} GiB, sm_{cap[0]}{cap[1]}")
        else:
            print(f"Device: cpu (torch {torch.__version__})")
            if requested == "auto" and "+cpu" in torch.__version__:
                print("  note: this is a CPU-only torch build, so no GPU would "
                      "be found even on a GPU node")
    return device


def env_int(name, default):
    """Read a positive int from the environment, falling back to `default`."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer; got {raw!r}")
    if value < 1:
        raise ValueError(f"{name} must be >= 1; got {value}")
    return value


def set_seed(default=42):
    """Seed python, numpy and torch from SEED; return the value used.

    Without this the finetuning runs were not reproducible and, worse, could
    not be repeated to estimate variance - every reported number was a single
    draw with no error bar.
    """
    import random

    seed = env_int("SEED", default)
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass
    print(f"Seed: {seed}")
    return seed


def anonymize_enabled():
    """True when ANONYMIZE_IDENTIFIERS is set to something truthy."""
    return os.environ.get("ANONYMIZE_IDENTIFIERS", "").lower() in (
        "1", "true", "yes", "on")


def run_tag():
    """Suffix distinguishing this run's output files.

    Set RUN_TAG explicitly, or let it be derived from the ablation and seed so
    that a matrix of runs cannot silently overwrite one another's results.
    """
    explicit = os.environ.get("RUN_TAG")
    if explicit:
        return explicit if explicit.startswith(("-", "_")) else "-" + explicit
    parts = []
    if anonymize_enabled():
        parts.append("anon")
    seed = os.environ.get("SEED")
    if seed and seed != "42":
        parts.append(f"seed{seed}")
    return ("-" + "-".join(parts)) if parts else ""
