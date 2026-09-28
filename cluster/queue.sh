#!/usr/bin/env bash
# Manage the shared job queue that lives on the NFS workdir.
#
#   ./cluster/queue.sh init                    # fill it with the full matrix
#   ./cluster/queue.sh init --jobs lora,full   # only these
#   ./cluster/queue.sh status                  # what is pending/running/done
#   ./cluster/queue.sh requeue <job>           # put a failed job back
#   ./cluster/queue.sh reset                   # wipe and start over
#
# The queue is a set of directories under $WORKDIR/queue. Workers on different
# machines claim jobs from it. Coordination is by directory creation, not by
# flock: flock's behaviour over NFS depends on the server, the client and the
# mount options, and a lock that silently does nothing would let two machines
# run the same job and overwrite each other's results. mkdir is atomic on NFS
# by specification.

set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"


ACTION="${1:-status}"; shift || true

load_config >/dev/null
Q="$(QUEUE_DIR)"

init_dirs() {
  mkdir -p "$Q/pending" "$Q/claimed" "$Q/done" "$Q/failed"
  [[ -e "$Q/.created" ]] || echo "$HOST $(date -Is)" > "$Q/.created"
}

case "$ACTION" in

  init)
    WANTED=""; FORCE=0
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --jobs)  WANTED="$2"; shift 2 ;;
        --force) FORCE=1; shift ;;
        *) die "usage: queue.sh init [--jobs a,b] [--force]" ;;
      esac
    done
    init_dirs
    n=0; skipped=()
    for spec in "${JOB_SPECS[@]}"; do
      name="${spec%%|*}"
      if [[ -n "$WANTED" ]] && ! grep -qw "$name" <<< "${WANTED//,/ }"; then
        continue
      fi
      if (( ! FORCE )); then
        # Two independent reasons to skip. The queue's own bookkeeping, and -
        # more reliably - the presence of the results file, which lives in the
        # repository and so is visible from every machine even if WORKDIR is
        # misconfigured. Without the second check, a queue on a non-shared
        # WORKDIR makes every init re-run the entire matrix.
        if [[ -e "$Q/pending/$name" ]]; then
          skipped+=("$name(already pending)"); continue
        fi
        if [[ -d "$Q/claimed/$name" ]]; then
          skipped+=("$name(running)"); continue
        fi
        if [[ -e "$Q/done/$name" ]]; then
          skipped+=("$name(done)"); continue
        fi
        rf="$(result_file_for_job "$spec" || true)"
        if [[ -n "$rf" && -s "$rf" ]]; then
          skipped+=("$name(has $(basename "$rf"))"); continue
        fi
      fi
      printf '%s\n' "$spec" > "$Q/pending/$name"
      n=$((n + 1))
    done

    echo "Queue:    $Q"
    echo "Queued:   $n job(s)"
    if (( ${#skipped[@]} )); then
      echo "Skipped:  ${skipped[*]}"
      echo "          (pass --force to run them again anyway)"
    fi
    echo
    echo "Now, on each GPU machine:"
    echo "  cd $REPO_DIR && ./cluster/setup.sh && ./cluster/worker.sh"
    ;;

  status)
    init_dirs
    printf '%-16s %s\n' "pending:" "$(ls -1 "$Q/pending" 2>/dev/null | tr '\n' ' ')"
    echo
    if [[ -n "$(ls -A "$Q/claimed" 2>/dev/null)" ]]; then
      echo "running:"
      for d in "$Q/claimed"/*; do
        [[ -d "$d" ]] || continue
        printf '  %-18s %s\n' "$(basename "$d")" "$(cat "$d/owner" 2>/dev/null || echo '?')"
      done
      echo
    fi
    printf '%-16s %s\n' "done:" "$(ls -1 "$Q/done" 2>/dev/null | tr '\n' ' ')"
    printf '%-16s %s\n' "failed:" "$(ls -1 "$Q/failed" 2>/dev/null | tr '\n' ' ')"
    ;;

  requeue)
    job="${1:?usage: queue.sh requeue <job>}"
    init_dirs
    for spec in "${JOB_SPECS[@]}"; do
      if [[ "${spec%%|*}" == "$job" ]]; then
        rm -rf "$Q/claimed/$job" "$Q/failed/$job" "$Q/done/$job"
        printf '%s\n' "$spec" > "$Q/pending/$job"
        echo "Requeued $job"
        exit 0
      fi
    done
    die "unknown job '$job'"
    ;;

  reset)
    read -r -p "Wipe the whole queue at $Q? [y/N] " a
    [[ "$a" == "y" ]] || { echo "aborted"; exit 0; }
    rm -rf "$Q"
    init_dirs
    echo "Queue reset. Results in dataset/finetune/outputs are untouched."
    ;;

  *)
    die "usage: queue.sh {init|status|requeue <job>|reset}"
    ;;
esac
