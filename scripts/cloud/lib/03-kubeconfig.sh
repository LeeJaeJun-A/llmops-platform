#!/bin/bash
# Step 3: Configure kubectl for EKS
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../shared" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/common.sh"

log_step "Step 3/11: Configure kubectl"

aws eks update-kubeconfig \
  --name "$CLUSTER_NAME" \
  --region "$AWS_REGION" > /dev/null 2>&1

wait_for "EKS nodes ready" \
  "kubectl get nodes --no-headers 2>/dev/null | grep -q ' Ready '" \
  300

NODE_COUNT=$(kubectl get nodes --no-headers 2>/dev/null | wc -l | tr -d ' ')
log_ok "kubectl configured — $NODE_COUNT nodes ready"
