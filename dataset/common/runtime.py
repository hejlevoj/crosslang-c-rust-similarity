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

    if announce:
        if device.type == "cuda":
            name = torch.cuda.get_device_name(0)
            total = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
            print(f"Device: cuda - {name}, {total:.1f} GiB")
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
