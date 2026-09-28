#!/usr/bin/env bash
# Pull jobs from the shared NFS queue and run them on this machine's GPUs.
#
# Run this on each GPU machine, after ./cluster/queue.sh init has been run
# once from anywhere:
#
#   cd <repo> && ./cluster/worker.sh
#   ./cluster/worker.sh --slots 2      # two concurrent jobs per GPU
#   ./cluster/worker.sh --gpus 1,3     # only these GPUs
#   ./cluster/worker.sh --once         # take one job and stop
#
# Machines join and leave freely: a worker exits when the queue is empty, and
# starting another one later picks up whatever has been added since. Nothing
# needs passwordless SSH, because the shared filesystem is the coordination
# channel rather than a control connection.

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

SLOTS_PER_GPU=1
GPU_LIST=""
ONCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --slots) SLOTS_PER_GPU="$2"; shift 2 ;;
    --gpus)  GPU_LIST="$2"; shift 2 ;;
    --once)  ONCE=1; shift ;;
    *) die "unknown option: $1  (see the header of $0)" ;;
  esac
done

load_config
load_modules
activate_venv
export_caches
report_gpu

Q="$(QUEUE_DIR)"
[[ -d "$Q/pending" ]] || die "no queue at $Q - run ./cluster/queue.sh init first"

if [[ -z "$GPU_LIST" ]]; then
  if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_LIST=$(nvidia-smi --query-gpu=index --format=csv,noheader | paste -sd, -)
  fi
  [[ -n "$GPU_LIST" ]] || die "no GPUs visible on $HOST. Pass --gpus, or run
  this on a machine that has one."
fi
IFS=',' read -r -a GPUS <<< "$GPU_LIST"

cd "$REPO_DIR"
LOGDIR="$WORKDIR/logs"; mkdir -p "$LOGDIR"
PIPE_REL="dataset/finetune/pipeline"
COMMIT="$(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"

echo "Worker:   $HOST, ${#GPUS[@]} GPU(s) x $SLOTS_PER_GPU slot(s)"
echo "Queue:    $Q"
echo

# Claim a job by creating its directory under claimed/. mkdir either creates
# the directory or fails because someone else already did; there is no window
# in which two machines both believe they won. Returns the spec on stdout.
claim() {
  local f name
  for f in "$Q"/pending/*; do
    [[ -e "$f" ]] || continue
    name="$(basename "$f")"
    if mkdir "$Q/claimed/$name" 2>/dev/null; then
      # We own it. Record who, then remove it from pending.
      echo "$HOST pid=$$ $(date -Is)" > "$Q/claimed/$name/owner"
      cat "$f" > "$Q/claimed/$name/spec" 2>/dev/null || true
      rm -f "$f"
      cat "$Q/claimed/$name/spec"
      return 0
    fi
  done
  return 1
}

run_job() {
  local gpu="$1" spec="$2"
  local name env_extra cmd log
  name="$(cut -d'|' -f1 <<< "$spec")"
  env_extra="$(cut -d'|' -f2 <<< "$spec" | xargs)"
  cmd="$(cut -d'|' -f3 <<< "$spec")"
  log="$LOGDIR/$name-$HOST-gpu$gpu-$(date +%Y%m%d-%H%M%S).log"

  {
    echo "=== $name on $HOST GPU $gpu at $(date -Is) ==="
    echo "commit:  $COMMIT"
    echo "env:     $env_extra BATCH_SIZE=${BATCH_SIZE:-} EPOCHS=${EPOCHS:-}"
    echo "command: $cmd"
    echo
  } > "$log"

  echo "  [start] $name  gpu $gpu  -> $(basename "$log")"

  if (
      cd "$PIPE_REL"
      export CUDA_VISIBLE_DEVICES="$gpu" DEVICE=cuda
      # shellcheck disable=SC2086
      env $env_extra bash -c "$cmd"
     ) >> "$log" 2>&1
  then
    echo "$HOST gpu$gpu $(date -Is)" > "$Q/done/$name"
    rm -rf "$Q/claimed/$name"
    echo "  [ok]    $name"
  else
    echo "$HOST gpu$gpu $(date -Is) log=$log" > "$Q/failed/$name"
    rm -rf "$Q/claimed/$name"
    echo "  [FAIL]  $name  -> $log"
  fi
}

slot_loop() {
  local gpu="$1"
  while :; do
    local spec
    if ! spec="$(claim)"; then
      break            # queue drained
    fi
    run_job "$gpu" "$spec"
    (( ONCE )) && break
  done
}

for gpu in "${GPUS[@]}"; do
  for ((s = 0; s < SLOTS_PER_GPU; s++)); do
    slot_loop "$gpu" &
  done
done
wait

echo
echo "Queue drained as far as this machine can see."
"$CLUSTER_DIR/queue.sh" status
