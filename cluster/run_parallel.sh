#!/usr/bin/env bash
# Run the experiment matrix across the GPUs on this host, one job per GPU at a
# time, pulling from a shared queue so a slow job does not idle the others.
#
#   CLUSTER=labic ./cluster/run_parallel.sh --list
#   CLUSTER=labic ./cluster/run_parallel.sh --dry-run
#   CLUSTER=labic ./cluster/run_parallel.sh
#   CLUSTER=labic ./cluster/run_parallel.sh --jobs lora,lora-anon
#   CLUSTER=labic ./cluster/run_parallel.sh --gpus 0,2
#
# Each job gets its own GPU via CUDA_VISIBLE_DEVICES, its own log, and a
# RUN_TAG that keeps its results file distinct. Nothing here shares state
# between jobs except the read-only dataset, so they cannot corrupt each
# other's output.

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

PIPE_REL="dataset/finetune/pipeline"


DRY=0
WANTED=""
GPU_LIST=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --jobs)    WANTED="$2"; shift 2 ;;
    --gpus)    GPU_LIST="$2"; shift 2 ;;
    --list)
      printf '%s\n' "${JOB_SPECS[@]}" | cut -d'|' -f1 | sed 's/^/  /'
      exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

load_config
load_modules
activate_venv
export_caches
report_gpu

# ------------------------------------------------------------------ gpu slots

if [[ -z "$GPU_LIST" ]]; then
  if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_LIST=$(nvidia-smi --query-gpu=index --format=csv,noheader | paste -sd, -)
  fi
  [[ -n "$GPU_LIST" ]] || die "no GPUs found. Pass --gpus explicitly, or run
  cluster/run.sh for a single CPU job."
fi
IFS=',' read -r -a GPUS <<< "$GPU_LIST"
echo "Slots:    ${#GPUS[@]} (GPUs ${GPUS[*]})"

# --------------------------------------------------------------- job selection

SELECTED=()
if [[ -n "$WANTED" ]]; then
  IFS=',' read -r -a want <<< "$WANTED"
  for w in "${want[@]}"; do
    found=0
    for spec in "${JOB_SPECS[@]}"; do
      [[ "${spec%%|*}" == "$w" ]] && { SELECTED+=("$spec"); found=1; break; }
    done
    (( found )) || die "unknown job '$w'. Try --list."
  done
else
  SELECTED=("${JOB_SPECS[@]}")
fi

echo "Jobs:     ${#SELECTED[@]}"
echo

# ------------------------------------------------------------------- the queue

cd "$REPO_DIR"
LOGDIR="$WORKDIR/logs"; mkdir -p "$LOGDIR"
STAMP="$(date +%Y%m%d-%H%M%S)"
QUEUE="$(mktemp)"; LOCK="$(mktemp)"
trap 'rm -f "$QUEUE" "$LOCK"' EXIT
printf '%s\n' "${SELECTED[@]}" > "$QUEUE"

COMMIT="$(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"

run_one() {
  local gpu="$1" spec="$2"
  local name env_extra cmd log
  name="$(cut -d'|' -f1 <<< "$spec")"
  env_extra="$(cut -d'|' -f2 <<< "$spec" | xargs)"
  cmd="$(cut -d'|' -f3 <<< "$spec")"
  log="$LOGDIR/$name-$STAMP.log"

  {
    echo "=== $name on $CLUSTER_NAME GPU $gpu at $(date -Is) ==="
    echo "commit:  $COMMIT"
    echo "env:     $env_extra RUN_TAG(auto) BATCH_SIZE=${BATCH_SIZE:-} EPOCHS=${EPOCHS:-}"
    echo "command: $cmd"
    echo
  } > "$log"

  if (( DRY )); then
    echo "  [dry] GPU $gpu  $name  <- $env_extra $cmd"
    return 0
  fi

  # DEVICE=cuda so a job that cannot see its GPU dies immediately instead of
  # silently running on CPU for hours.
  if (
      cd "$PIPE_REL"
      export CUDA_VISIBLE_DEVICES="$gpu" DEVICE=cuda
      # shellcheck disable=SC2086
      env $env_extra bash -c "$cmd"
     ) >> "$log" 2>&1
  then
    echo "  [ok  ] GPU $gpu  $name"
  else
    echo "  [FAIL] GPU $gpu  $name  -> $log"
    return 1
  fi
}

worker() {
  local gpu="$1"
  while :; do
    local spec
    spec="$(flock "$LOCK" bash -c "head -n1 '$QUEUE'; sed -i '1d' '$QUEUE'")"
    [[ -n "$spec" ]] || break
    run_one "$gpu" "$spec" || true
  done
}

echo "Starting. Logs in $LOGDIR/<job>-$STAMP.log"
echo
for gpu in "${GPUS[@]}"; do
  worker "$gpu" &
done
wait

echo
echo "All jobs finished. Results:"
ls -1 "$REPO_DIR/dataset/finetune/outputs"/results_*.json 2>/dev/null | sed 's|.*/|  |' || true
echo
echo "Summarise with:  python dataset/scripts/summarize_results.py"
