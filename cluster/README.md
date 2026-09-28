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
| `TORCH_CUDA` | `nvidia-smi` → read `CUDA Version` in the header, then see the table below. Default `cu126` |
| `WORKDIR` | `df -h ~ /scratch /work /data 2>/dev/null` — pick a filesystem with tens of GB free, **not** `$HOME` |
| `PYTHON_BIN` | after `module load`, `python3 -V` — must be ≥3.9 |
| `BATCH_SIZE` | start at the shipped default, then watch `nvidia-smi` and raise until memory is ~80% used |

### torch must be >= 2.6

`microsoft/unixcoder-base` publishes only `pytorch_model.bin` — no safetensors —
so `transformers` has to go through `torch.load`, and it refuses to do that on
torch older than 2.6 (CVE-2025-32434). A run on an older torch gets all the way
to `from_pretrained` and then dies with a `ValueError`.

The trap is that the CUDA index caps the torch version, quietly:

| Index | Highest torch | |
|---|---|---|
| `cu118` | 2.7.1 | ok |
| `cu121` | 2.5.1 | **too old — never use** |
| `cu124` | 2.6.0 | ok, only just |
| `cu126` | 2.14.0 | preferred, the default |
| `cu128` | 2.11.0 | ok |

`setup.sh` now installs `torch>=2.6` explicitly, so an index that cannot
satisfy it fails at install time with a resolver error rather than an hour
later at model load. CUDA 12.x drivers are minor-version compatible, so a 12.x
driver generally runs any `cu12x` build.

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

## Running the matrix across several machines

The GPUs at Labic live on machines other than the access host, SSH between
them asks for a password, and `$WORKDIR` is shared over NFS. That rules out
an orchestrator that drives the other machines — but it makes the shared
filesystem itself the coordination channel, which is simpler and needs no
credentials.

**Once, from anywhere:**

```bash
./cluster/queue.sh init
```

**Then on each GPU machine**, after logging in:

```bash
cd <repo> && ./cluster/setup.sh && ./cluster/worker.sh
```

A worker claims jobs from the shared queue until it is empty, then exits.
Machines join and leave freely; starting another worker later picks up
whatever has been added since. Watch progress from anywhere with
`./cluster/queue.sh status`.

```bash
./cluster/worker.sh --slots 2    # two concurrent jobs per GPU
./cluster/worker.sh --gpus 1,3   # only these GPUs
./cluster/worker.sh --once       # take one job and stop
```

Jobs are ordered longest-first, so the tail is not one full finetune running
alone while everything else sits idle.

### Two details this setup forces

**The venv is per host, the model cache is not.** `setup.sh` builds
`$WORKDIR/venv-<hostname>`. The machines carry different GPUs and CUDA
versions, so they need different torch builds, and a single shared venv would
leave whichever host ran `setup.sh` last silently deciding what every other
host runs. The Hugging Face cache under `$WORKDIR/hf` *is* shared on purpose —
the weights are identical everywhere, so the first machine to run pays the
download for all of them.

**Claiming uses `mkdir`, not `flock`.** `flock` over NFS depends on the
server, the client and the mount options, and a lock that silently does
nothing would let two machines run the same job and overwrite each other's
results. Directory creation is atomic on NFS by specification. Verified with
eight concurrent claimers over 40 jobs: 40 claims, no duplicates.

### Per-host configuration

A config named after the machine wins over the site config, so hosts with
different hardware can differ:

```bash
cp cluster/config/labic.env cluster/config/$(hostname -s).env
# then edit MODULES, TORCH_CUDA and BATCH_SIZE for that machine
```

`worker.sh` prints which config and which venv it picked at startup.

### Single machine with several GPUs

`run_parallel.sh` is the older, simpler runner for that case: no queue, no
shared state, just the matrix spread over local GPUs.

```bash
CLUSTER=labic ./cluster/run_parallel.sh --list
CLUSTER=labic ./cluster/run_parallel.sh --dry-run
CLUSTER=labic ./cluster/run_parallel.sh --jobs lora,lora-anon
```

Both runners read the same `JOB_SPECS` from `common.sh`, so the matrix cannot
drift between them.

The matrix covers three questions the single-run results left open:

| Jobs | Question |
|---|---|
| `lora`, `lora-seed43/44/45` | How much of the reported number is seed noise? Everything so far is a single draw with no error bar. |
| `*-anon` | How much of the performance is identifier overlap rather than structure? |
| `lexical`, `lexical-anon` | Does a model beat plain name matching? Zero-shot UniXcoder does not. |

Collect everything afterwards:

```bash
python dataset/scripts/summarize_results.py
python dataset/scripts/summarize_results.py --latex   # rows for the paper
```

The summariser folds `-seedNN` variants of a configuration together and reports
mean ± standard deviation across them.

---

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
