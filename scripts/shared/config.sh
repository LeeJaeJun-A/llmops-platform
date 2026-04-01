#!/bin/bash
# =============================================================================
# LLMOps Platform — Deployment Configuration
# Single source of truth for all deployment scripts
# =============================================================================

# --- AWS ---
export AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-CHANGE_ME}"
export AWS_REGION="ap-northeast-2"

# --- Project ---
export PROJECT_NAME="llmops"
export ENVIRONMENT="dev"

# --- Derived ---
export CLUSTER_NAME="${PROJECT_NAME}-${ENVIRONMENT}"
export ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT_NAME}-platform"
export STATE_BUCKET="${PROJECT_NAME}-tfstate-${ENVIRONMENT}-${AWS_ACCOUNT_ID}"
export LOCK_TABLE="${PROJECT_NAME}-tflock-${ENVIRONMENT}-${AWS_ACCOUNT_ID}"
export TF_DIR="infra/live/aws/${ENVIRONMENT}"
export HELM_CHART="helm/llmops-platform"
export HELM_VALUES="${HELM_CHART}/values-${ENVIRONMENT}.yaml"
export HELM_RELEASE="llmops"
export KARPENTER_VERSION="1.1.1"
export LANGFUSE_NAMESPACE="langfuse"
export KARPENTER_NAMESPACE="karpenter"

# --- Paths ---
export PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export SCRIPTS_DIR="${PROJECT_ROOT}/scripts"
export SHARED_DIR="${SCRIPTS_DIR}/shared"
export TF_OUTPUTS="/tmp/llmops-tf-outputs.env"
