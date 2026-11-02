#!/usr/bin/env bash
# Shared shell setup: pick a host config, load modules, activate the venv.
# Sourced by setup.sh and run.sh; not meant to be executed directly.

set -euo pipefail

CLUSTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$CLUSTER_DIR/.." && pwd)"

die() { echo "error: $*" >&2; exit 1; }

# ---------------------------------------------------------------- host config

# Order: explicit $CLUSTER, else guess from the hostname, else fail loudly.
# Guessing silently wrong would send a job to the wrong filesystem, so an
# unrecognised host is an error rather than a default.
HOST="$(hostname -s 2>/dev/null || echo unknown)"

# A config named after this exact host wins, so machines with different GPUs or
# CUDA versions can each carry their own settings; otherwise fall back to the
# site config.
pick_cluster() {
  if [[ -f "$CLUSTER_DIR/config/$HOST.env" ]]; then
    echo "$HOST"; return
  fi
  if [[ -n "${CLUSTER:-}" ]]; then
    echo "$CLUSTER"; return
  fi
  case "$HOST" in
    *labic*) echo labic ;;
    *cdi*)   echo cdi ;;
    *) die "cannot tell which cluster this is from the hostname '$HOST'.
  Set it explicitly:  CLUSTER=labic $0 ...   (or CLUSTER=cdi)
  Or add a per-host config at cluster/config/$HOST.env
  Configs available:  $(cd "$CLUSTER_DIR/config" && ls *.env | tr '\n' ' ')" ;;
  esac
}

load_config() {
  CLUSTER="$(pick_cluster)"
  local cfg="$CLUSTER_DIR/config/$CLUSTER.env"
  [[ -f "$cfg" ]] || die "no config at $cfg"
  # shellcheck disable=SC1090
  source "$cfg"
  echo "Cluster:  $CLUSTER_NAME"
  echo "Workdir:  $WORKDIR"

  if grep -q 'TODO' "$cfg"; then
    echo
    echo "warning: $cfg still has TODO markers. Fill them in before trusting a"
    echo "         long run — see cluster/README.md for the discovery commands."
    echo
  fi
}

# --------------------------------------------------------------- environment

load_modules() {
  if [[ "${#MODULES[@]}" -eq 0 ]]; then
    echo "Modules:  none configured"
    return
  fi
  if ! command -v module >/dev/null 2>&1; then
    die "MODULES is set in the config but there is no 'module' command here.
  Either clear MODULES or check that Lmod is initialised for non-interactive
  shells (some sites only set it up in ~/.bashrc for login shells)."
  fi
  for m in "${MODULES[@]}"; do
    echo "Loading module $m"
    module load "$m"
  done
}

# One venv per host, even though WORKDIR is shared over NFS. The machines
# carry different GPUs and CUDA versions, so they need different torch builds;
# a single shared venv would have whichever host ran setup.sh last silently
# deciding what every other host runs.
VENV_DIR() { echo "$WORKDIR/venv-$HOST"; }

activate_venv() {
  local venv; venv="$(VENV_DIR)"
  [[ -f "$venv/bin/activate" ]] || die "no venv at $venv — run cluster/setup.sh first"
  # shellcheck disable=SC1091
  source "$venv/bin/activate"
  echo "Python:   $(python -V 2>&1) at $(command -v python)"
}

# Keep the model cache out of $HOME: it holds several GB per model and home
# quotas on shared machines are routinely smaller than that. Unlike the venv,
# this one is deliberately shared across hosts - the weights are identical
# everywhere, so the first machine to run pays the download for all of them.
export_caches() {
  export HF_HOME="$WORKDIR/hf"
  export TRANSFORMERS_CACHE="$HF_HOME/transformers"
  export TORCH_HOME="$WORKDIR/torch"
  mkdir -p "$HF_HOME" "$TORCH_HOME"
  echo "HF_HOME:  $HF_HOME"
}

QUEUE_DIR() { echo "$WORKDIR/queue"; }

report_gpu() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=index,name,memory.total,memory.used \
               --format=csv,noheader 2>/dev/null | sed 's/^/GPU:      /'
  else
    echo "GPU:      no nvidia-smi on this host"
  fi
}

# ----------------------------------------------------------------- job matrix
#
# name | extra env | command, run from dataset/finetune/pipeline.
# Defined here so queue.sh and run_parallel.sh cannot drift apart.
# Ordered longest-first: both runners are greedy, so starting with the full
# finetunes keeps the tail from being one long job running alone.
JOB_SPECS=(
  "full|                                  |python finetune_st.py"
  "full-anon|ANONYMIZE_IDENTIFIERS=1      |python finetune_st.py"
  "lora|                                  |python finetune_lora.py"
  "lora-anon|ANONYMIZE_IDENTIFIERS=1      |python finetune_lora.py"
  "lora-seed43|SEED=43                    |python finetune_lora.py"
  "lora-seed44|SEED=44                    |python finetune_lora.py"
  "lora-seed45|SEED=45                    |python finetune_lora.py"
  "baseline|                              |python baseline_eval.py"
  "baseline-anon|ANONYMIZE_IDENTIFIERS=1  |python baseline_eval.py"
  "lexical|                               |python lexical_baseline.py"
  "lexical-anon|ANONYMIZE_IDENTIFIERS=1   |python lexical_baseline.py"
)

job_spec() {
  local want="$1" spec
  for spec in "${JOB_SPECS[@]}"; do
    [[ "${spec%%|*}" == "$want" ]] && { printf '%s\n' "$spec"; return 0; }
  done
  return 1
}

# Results file a job will write, derived from its spec the same way
# dataset/common/runtime.py:run_tag() derives it. Used by queue.sh to avoid
# re-queueing work that is already done - a check that holds even when
# WORKDIR is misconfigured, because the results live in the repository, which
# every machine reads from by definition.
result_file_for_job() {
  local spec="$1" cmd env_extra stem tag=""
  cmd="$(cut -d'|' -f3 <<< "$spec")"
  env_extra="$(cut -d'|' -f2 <<< "$spec")"

  case "$cmd" in
    *finetune_st.py*)     stem=st ;;
    *finetune_lora.py*)   stem=lora ;;
    *baseline_eval.py*)   stem=baseline ;;
    *lexical_baseline.py*) stem=lexical ;;
    *) return 1 ;;
  esac

  [[ "$env_extra" == *ANONYMIZE_IDENTIFIERS=1* ]] && tag="-anon"
  if [[ "$env_extra" =~ SEED=([0-9]+) ]]; then
    [[ "${BASH_REMATCH[1]}" != "42" ]] && tag="$tag-seed${BASH_REMATCH[1]}"
  fi

  echo "$REPO_DIR/dataset/finetune/outputs/results_${stem}${tag}.json"
}

# ------------------------------------------------- experiment hyperparameters
#
# These are properties of the EXPERIMENT, not of the machine, and they live
# here rather than in the per-host configs on purpose. The training loss is
# InfoNCE over in-batch negatives, so batch size changes how many negatives
# each step sees and therefore the training signal itself. A host with more
# GPU memory running a bigger batch would produce a number that cannot be
# compared with the others - and would silently confound the seed runs, whose
# whole purpose is to measure variance.
#
# Change them for the whole matrix or not at all, and report the value used.
export BATCH_SIZE="${BATCH_SIZE:-32}"
export EVAL_BATCH_SIZE="${EVAL_BATCH_SIZE:-64}"
export EPOCHS="${EPOCHS:-5}"

warn_hyperparameter_override() {
  local f="$1"
  if grep -qE '^\s*export\s+(BATCH_SIZE|EPOCHS|EVAL_BATCH_SIZE)=' "$f" 2>/dev/null; then
    echo
    echo "WARNING: $f overrides a training hyperparameter."
    echo "         Runs from this host will not be comparable with the others."
    echo
  fi
}
