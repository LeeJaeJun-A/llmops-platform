#!/bin/bash
# Shared functions for all deployment scripts

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_step() { echo -e "${BLUE}==>${NC} $1"; }
log_ok()   { echo -e "${GREEN} ✓${NC} $1"; }
log_warn() { echo -e "${YELLOW} !${NC} $1"; }
log_err()  { echo -e "${RED} ✗${NC} $1"; }
log_info() { echo -e "   $1"; }

# Run a command, show error on failure
run() {
  if "$@" > /dev/null 2>&1; then
    return 0
  else
    log_err "Command failed: $*"
    return 1
  fi
}

# Wait for a condition with timeout
wait_for() {
  local desc="$1" cmd="$2" timeout="${3:-300}" interval="${4:-10}"
  local elapsed=0
  log_info "Waiting for ${desc}..."
  while ! eval "$cmd" > /dev/null 2>&1; do
    sleep "$interval"
    elapsed=$((elapsed + interval))
    if [ "$elapsed" -ge "$timeout" ]; then
      log_err "Timeout waiting for ${desc} (${timeout}s)"
      return 1
    fi
  done
  log_ok "$desc"
}

# Check if a command exists
require_cmd() {
  for cmd in "$@"; do
    if ! command -v "$cmd" &>/dev/null; then
      log_err "Required command not found: $cmd"
      exit 1
    fi
  done
}

# Load terraform outputs from temp file
load_tf_outputs() {
  if [ -f "$TF_OUTPUTS" ]; then
    source "$TF_OUTPUTS"
  fi
}

# Save a terraform output to temp file
save_tf_output() {
  local key="$1" value="$2"
  echo "export ${key}=\"${value}\"" >> "$TF_OUTPUTS"
}
