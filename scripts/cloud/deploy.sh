#!/bin/bash
# =============================================================================
# LLMOps Platform — One-Click Cloud Deployment
# Deploys the full stack from scratch to AWS EKS
# Usage: ./scripts/cloud/deploy.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOUD_LIB="${SCRIPT_DIR}/lib"
source "${SCRIPT_DIR}/../shared/config.sh"
source "${SCRIPT_DIR}/../shared/common.sh"

echo ""
echo "============================================"
echo "  LLMOps Platform — Cloud Deploy"
echo "  Account: ${AWS_ACCOUNT_ID}"
echo "  Region:  ${AWS_REGION}"
echo "  Env:     ${ENVIRONMENT}"
echo "============================================"
echo ""

# Pre-flight checks
log_step "Pre-flight checks"
require_cmd aws terraform terragrunt helm kubectl docker python3

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  log_err "AWS credentials not configured. Run: aws configure"
  exit 1
fi
log_ok "AWS credentials valid"

if [ ! -f "${PROJECT_ROOT}/.env.secrets" ]; then
  log_err ".env.secrets not found"
  log_info "Create from template: cp .env.secrets.example .env.secrets"
  log_info "Fill in your ANTHROPIC_API_KEY and GEMINI_API_KEY"
  exit 1
fi
log_ok ".env.secrets found"

if ! docker info >/dev/null 2>&1; then
  log_err "Docker is not running"
  exit 1
fi
log_ok "Docker running"

echo ""

# Execute all steps
START_TIME=$(date +%s)

source "${CLOUD_LIB}/01-state-infra.sh"
echo ""
source "${CLOUD_LIB}/02-terraform.sh"
echo ""
source "${CLOUD_LIB}/03-kubeconfig.sh"
echo ""
source "${CLOUD_LIB}/04-ebs-csi.sh"
echo ""
source "${CLOUD_LIB}/05-karpenter-helm.sh"
echo ""
source "${CLOUD_LIB}/06-karpenter-iam-fix.sh"
echo ""
source "${CLOUD_LIB}/07-docker-build.sh"
echo ""
source "${CLOUD_LIB}/08-helm-deploy.sh"
echo ""
source "${CLOUD_LIB}/09-db-migrate.sh"
echo ""
source "${CLOUD_LIB}/10-langfuse.sh"
echo ""
source "${CLOUD_LIB}/11-verify.sh"

END_TIME=$(date +%s)
ELAPSED=$(( END_TIME - START_TIME ))
MINUTES=$(( ELAPSED / 60 ))
SECONDS_REMAINING=$(( ELAPSED % 60 ))

echo ""
echo "============================================"
echo -e "  ${GREEN}Cloud deployment complete!${NC}"
echo "  Time: ${MINUTES}m ${SECONDS_REMAINING}s"
echo "  Cost: ~\$0.50/hr (~\$12/day)"
echo ""
echo "  App:      kubectl port-forward svc/${HELM_RELEASE}-llmops-platform 8000:8000"
echo "  Langfuse: kubectl port-forward svc/langfuse-web 3000:3000 -n langfuse"
echo ""
echo "  Teardown: ./scripts/cloud/teardown.sh"
echo "============================================"
