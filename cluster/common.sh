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
pick_cluster() {
  if [[ -n "${CLUSTER:-}" ]]; then
    echo "$CLUSTER"; return
  fi
  case "$(hostname -s 2>/dev/null || echo unknown)" in
    *labic*) echo labic ;;
    *cdi*)   echo cdi ;;
    *) die "cannot tell which cluster this is from the hostname.
  Set it explicitly:  CLUSTER=labic $0 ...   (or CLUSTER=cdi)
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

VENV_DIR() { echo "$WORKDIR/venv"; }

activate_venv() {
  local venv; venv="$(VENV_DIR)"
  [[ -f "$venv/bin/activate" ]] || die "no venv at $venv — run cluster/setup.sh first"
  # shellcheck disable=SC1091
  source "$venv/bin/activate"
  echo "Python:   $(python -V 2>&1) at $(command -v python)"
}

# Keep the model cache out of $HOME: it holds several GB per model and home
# quotas on shared machines are routinely smaller than that.
export_caches() {
  export HF_HOME="$WORKDIR/hf"
  export TRANSFORMERS_CACHE="$HF_HOME/transformers"
  export TORCH_HOME="$WORKDIR/torch"
  mkdir -p "$HF_HOME" "$TORCH_HOME"
  echo "HF_HOME:  $HF_HOME"
}

report_gpu() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi --query-gpu=index,name,memory.total,memory.used \
               --format=csv,noheader 2>/dev/null | sed 's/^/GPU:      /'
  else
    echo "GPU:      no nvidia-smi on this host"
  fi
}
