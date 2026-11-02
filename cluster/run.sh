#!/usr/bin/env bash
# Launch a pipeline job, detached, with logging.
#
#   CLUSTER=labic ./cluster/run.sh categorize
#   CLUSTER=cdi   ./cluster/run.sh baseline
#   CLUSTER=cdi   ./cluster/run.sh lora
#   CLUSTER=cdi   ./cluster/run.sh full
#   CLUSTER=cdi   ./cluster/run.sh all
#
# There is no scheduler on these hosts, so the job goes under nohup and
# survives the SSH session. Logs land in $WORKDIR/logs/<job>-<timestamp>.log
# and the tail command is printed at the end.
#
# Add --fg to run in the foreground instead (useful for a first smoke run).

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

JOB="${1:-}"
FOREGROUND=""
[[ "${2:-}" == "--fg" || "${1:-}" == "--fg" ]] && FOREGROUND=1
[[ "$JOB" == "--fg" ]] && JOB="${2:-}"

usage() {
  cat >&2 <<EOF
usage: CLUSTER=<labic|cdi> $0 <job> [--fg]

jobs:
  categorize   SFR difficulty labels over the whole dataset, writes back
               difficulty + difficulty_score, then re-stratifies the split
  baseline     zero-shot UniXcoder retrieval on val and test
  lora         LoRA finetune + evaluation
  full         full-parameter finetune + evaluation
  all          baseline, then lora, then full, in sequence
EOF
  exit 2
}

[[ -n "$JOB" ]] || usage

load_config
load_modules
activate_venv
export_caches
report_gpu

cd "$REPO_DIR"
LOGDIR="$WORKDIR/logs"; mkdir -p "$LOGDIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$LOGDIR/$JOB-$STAMP.log"

# The finetune scripts import a sibling `evaluate` module, so they must run
# with their own directory first on sys.path.
PIPE="$REPO_DIR/dataset/finetune/pipeline"

build_command() {
  case "$JOB" in
    categorize)
      echo "python '$REPO_DIR/dataset/categorization/categorize.py' --write-labels \
&& python '$REPO_DIR/dataset/scripts/build_dataset_v1.py' --write \
&& python '$REPO_DIR/dataset/scripts/smoke_test.py'"
      ;;
    baseline) echo "cd '$PIPE' && python baseline_eval.py" ;;
    lora)     echo "cd '$PIPE' && python finetune_lora.py" ;;
    full)     echo "cd '$PIPE' && python finetune_st.py" ;;
    all)
      echo "cd '$PIPE' && python baseline_eval.py && python finetune_lora.py && python finetune_st.py"
      ;;
    *) usage ;;
  esac
}

CMD="$(build_command)"

echo
echo "Job:      $JOB"
echo "Batch:    BATCH_SIZE=${BATCH_SIZE:-default} EVAL_BATCH_SIZE=${EVAL_BATCH_SIZE:-default} EPOCHS=${EPOCHS:-default}"
echo "Log:      $LOG"
echo

{
  echo "=== $JOB on $CLUSTER_NAME at $(date -Is) ==="
  echo "commit:  $(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  echo "host:    $(hostname)"
  echo "command: $CMD"
  echo "env:     BATCH_SIZE=${BATCH_SIZE:-} EVAL_BATCH_SIZE=${EVAL_BATCH_SIZE:-} EPOCHS=${EPOCHS:-} DEVICE=${DEVICE:-auto}"
  echo
} > "$LOG"

if [[ -n "$FOREGROUND" ]]; then
  bash -c "$CMD" 2>&1 | tee -a "$LOG"
else
  nohup bash -c "$CMD" >> "$LOG" 2>&1 &
  echo "Started as PID $! (detached; safe to close the SSH session)"
  echo
  echo "  tail -f $LOG"
  echo "  kill $!"
fi
