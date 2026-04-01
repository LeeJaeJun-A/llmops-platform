#!/bin/bash
# Step 5: Install Karpenter Helm chart
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../shared" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/common.sh"
load_tf_outputs

log_step "Step 5/11: Karpenter Helm install"

CLUSTER_ENDPOINT="${TF_CLUSTER_ENDPOINT:-$(aws eks describe-cluster --name $CLUSTER_NAME --region $AWS_REGION --query 'cluster.endpoint' --output text)}"
KARPENTER_ROLE="${TF_KARPENTER_ROLE_ARN:-arn:aws:iam::${AWS_ACCOUNT_ID}:role/${CLUSTER_NAME}-karpenter-controller}"

helm upgrade --install karpenter oci://public.ecr.aws/karpenter/karpenter \
  --namespace "$KARPENTER_NAMESPACE" --create-namespace \
  --version "$KARPENTER_VERSION" \
  --set "settings.clusterName=${CLUSTER_NAME}" \
  --set "settings.clusterEndpoint=${CLUSTER_ENDPOINT}" \
  --set "settings.interruptionQueue=${CLUSTER_NAME}-karpenter" \
  --set "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn=${KARPENTER_ROLE}" \
  --set "replicas=1" \
  --wait --timeout 5m > /dev/null 2>&1

log_ok "Karpenter installed (v${KARPENTER_VERSION})"
