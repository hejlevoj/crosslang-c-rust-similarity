# Running on Labic and CDI

Both hosts are accessed over SSH with no batch scheduler, so jobs run under
`nohup` and survive the session. Python comes from `module load` plus a
per-project virtualenv.

```bash
git clone <repo> && cd crosslang-c-rust-similarity
CLUSTER=labic ./cluster/setup.sh          # once per host
CLUSTER=labic ./cluster/run.sh categorize
```

`CLUSTER` may be omitted if the hostname contains `labic` or `cdi`; otherwise
it is required. An unrecognised host is an error rather than a default, so a
job never silently lands on the wrong filesystem.

---

## First: fill in the host config

`config/labic.env` and `config/cdi.env` ship with `TODO` markers, because
nothing in them can be guessed from here — they are properties of machines this
repository has never seen. `setup.sh` and `run.sh` both warn while any `TODO`
remains.

Run these on the host and copy the answers in:

| Setting | How to find it |
|---|---|
| `MODULES` | `module avail 2>&1 \| grep -i -E 'python\|cuda'` — take the Python and CUDA modules, in load order |
| `TORCH_CUDA` | `nvidia-smi` → read `CUDA Version` in the header. 12.1 → `cu121`, 12.4 → `cu124`, 11.8 → `cu118` |
| `WORKDIR` | `df -h ~ /scratch /work /data 2>/dev/null` — pick a filesystem with tens of GB free, **not** `$HOME` |
| `PYTHON_BIN` | after `module load`, `python3 -V` — must be ≥3.9 |
| `BATCH_SIZE` | start at the shipped default, then watch `nvidia-smi` and raise until memory is ~80% used |

Quick one-liner to gather most of it:

```bash
hostname -s; nvidia-smi | head -12; module avail 2>&1 | grep -i -E 'python|cuda'; df -h ~ /scratch /work 2>/dev/null
```

---

## Jobs

| Job | What it does | Depends on |
|---|---|---|
| `categorize` | SFR difficulty labels over the whole dataset, writes `difficulty` + `difficulty_score` back, re-stratifies the split, re-runs the smoke test | — |
| `baseline` | Zero-shot UniXcoder retrieval on val and test | `categorize` |
| `lora` | LoRA finetune + evaluation | `categorize` |
| `full` | Full-parameter finetune + evaluation | `categorize` |
| `all` | `baseline`, then `lora`, then `full` | `categorize` |

Run `categorize` first and let it finish. It rewrites `dataset.jsonl`,
including the `split` field, so anything started before it completes would be
training against a split that is about to change.

```bash
CLUSTER=cdi ./cluster/run.sh categorize     # then, once it is done:
CLUSTER=cdi ./cluster/run.sh all
```

Add `--fg` to keep a job in the foreground — worth doing for the first run on a
new host, so a misconfiguration surfaces immediately instead of in a log.

Logs go to `$WORKDIR/logs/<job>-<timestamp>.log` and record the commit, host,
command and the batch-size environment for the run, so a result can be traced
back to what produced it.

---

## Why the device handling changed

The pipelines used to hardcode `torch.device("cpu")`. On a GPU host that is
silently wrong in the worst way: the job runs, produces correct numbers, and
takes twenty hours instead of twenty minutes. They now call
`dataset/common/runtime.py:get_device()`, which picks CUDA when it is there and
prints what it chose.

Two things that follow from that, both worth checking on the first run:

- **`torch` must be a CUDA build.** `setup.sh` installs it from the PyTorch
  index matching `TORCH_CUDA` *before* the requirements files, because
  installing it as a transitive dependency would pull whatever wheel PyPI
  defaults to. If `setup.sh`'s verification step says `cuda available: False`,
  stop and fix `TORCH_CUDA` — do not start a long job.
- **`DEVICE=cuda` forces the issue.** With the default `DEVICE=auto` a missing
  GPU degrades quietly to CPU. Setting `DEVICE=cuda` makes the job fail at
  startup instead, which is what you want for an overnight run:

  ```bash
  DEVICE=cuda CLUSTER=cdi ./cluster/run.sh full
  ```

## Tuning

`BATCH_SIZE`, `EVAL_BATCH_SIZE` and `EPOCHS` are read from the environment by
`dataset/common/runtime.py`. The defaults in the code (8 and 16) were chosen to
fit a few GB of CPU RAM and are far too small for a GPU; the host configs raise
them to 32 and 64 as a starting point.

Note that `BATCH_SIZE` is not a free parameter here. The training loss is
InfoNCE over in-batch negatives, so a larger batch means more negatives per
step and a genuinely different — generally stronger — training signal. Changing
it changes the result, not just the throughput. Keep it fixed across the runs
you intend to compare, and report it in the paper.
