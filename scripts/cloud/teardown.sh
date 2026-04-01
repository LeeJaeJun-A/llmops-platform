#!/bin/bash
# =============================================================================
# LLMOps Platform — Full Teardown
# Destroys all AWS resources to stop charges
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../shared/config.sh"
source "${SCRIPT_DIR}/../shared/common.sh"

echo ""
echo "============================================"
echo -e "  ${RED}LLMOps Platform — TEARDOWN${NC}"
echo "  Account: ${AWS_ACCOUNT_ID}"
echo "  Region:  ${AWS_REGION}"
echo "  Env:     ${ENVIRONMENT}"
echo "============================================"
echo ""
echo -e "${YELLOW}This will DESTROY all AWS resources.${NC}"
echo ""
read -p "Type 'destroy' to confirm: " CONFIRM

if [ "$CONFIRM" != "destroy" ]; then
  echo "Aborted."
  exit 0
fi

echo ""

# Step 1: Helm releases
log_step "Step 1/5: Helm uninstall"

# Kill port-forwards
kill $(lsof -ti:8000) 2>/dev/null || true
kill $(lsof -ti:3000) 2>/dev/null || true

if helm status "$HELM_RELEASE" >/dev/null 2>&1; then
  helm uninstall "$HELM_RELEASE" > /dev/null 2>&1
  log_ok "Uninstalled: $HELM_RELEASE"
else
  log_info "Not found: $HELM_RELEASE (skipped)"
fi

# Delete Karpenter NodePool/EC2NodeClass first (prevents orphaned nodes)
kubectl delete nodepools --all 2>/dev/null || true
kubectl delete ec2nodeclasses --all 2>/dev/null || true

if helm status langfuse -n "$LANGFUSE_NAMESPACE" >/dev/null 2>&1; then
  helm uninstall langfuse -n "$LANGFUSE_NAMESPACE" > /dev/null 2>&1
  kubectl delete pvc --all -n "$LANGFUSE_NAMESPACE" 2>/dev/null || true
  log_ok "Uninstalled: langfuse"
else
  log_info "Not found: langfuse (skipped)"
fi

if helm status karpenter -n "$KARPENTER_NAMESPACE" >/dev/null 2>&1; then
  helm uninstall karpenter -n "$KARPENTER_NAMESPACE" > /dev/null 2>&1
  log_ok "Uninstalled: karpenter"
else
  log_info "Not found: karpenter (skipped)"
fi

echo ""

# Step 2: Terraform destroy
log_step "Step 2/5: Terraform destroy (this takes 10-15 minutes)"

if [ -d "${PROJECT_ROOT}/${TF_DIR}" ]; then
  cd "${PROJECT_ROOT}/${TF_DIR}"
  terragrunt run-all destroy --terragrunt-non-interactive -auto-approve 2>&1 | tail -5
  log_ok "Terraform resources destroyed"
else
  log_info "Terraform directory not found (skipped)"
fi

echo ""

# Step 3: ECR repository
log_step "Step 3/5: Delete ECR repository"
if aws ecr describe-repositories --repository-names "${PROJECT_NAME}-platform" --region "$AWS_REGION" >/dev/null 2>&1; then
  aws ecr delete-repository \
    --repository-name "${PROJECT_NAME}-platform" \
    --force --region "$AWS_REGION" > /dev/null
  log_ok "Deleted ECR: ${PROJECT_NAME}-platform"
else
  log_info "ECR not found (skipped)"
fi

echo ""

# Step 4: State infrastructure
log_step "Step 4/5: Delete state infrastructure"

if aws s3api head-bucket --bucket "$STATE_BUCKET" --region "$AWS_REGION" 2>/dev/null; then
  aws s3 rb "s3://${STATE_BUCKET}" --force > /dev/null 2>&1
  log_ok "Deleted S3: $STATE_BUCKET"
else
  log_info "S3 bucket not found (skipped)"
fi

if aws dynamodb describe-table --table-name "$LOCK_TABLE" --region "$AWS_REGION" >/dev/null 2>&1; then
  aws dynamodb delete-table --table-name "$LOCK_TABLE" --region "$AWS_REGION" > /dev/null
  log_ok "Deleted DynamoDB: $LOCK_TABLE"
else
  log_info "DynamoDB table not found (skipped)"
fi

echo ""

# Step 5: Manually created IAM roles
log_step "Step 5/5: Cleanup IAM roles"

LANGFUSE_SM_NAME="${PROJECT_NAME}/${ENVIRONMENT}/langfuse"
if aws secretsmanager describe-secret --secret-id "$LANGFUSE_SM_NAME" --region "$AWS_REGION" >/dev/null 2>&1; then
  aws secretsmanager delete-secret --secret-id "$LANGFUSE_SM_NAME" --region "$AWS_REGION" --force-delete-without-recovery > /dev/null
  log_ok "Deleted secret: $LANGFUSE_SM_NAME"
else
  log_info "Secret not found: $LANGFUSE_SM_NAME (skipped)"
fi

EBS_ROLE="${CLUSTER_NAME}-ebs-csi"
if aws iam get-role --role-name "$EBS_ROLE" >/dev/null 2>&1; then
  aws iam detach-role-policy --role-name "$EBS_ROLE" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy 2>/dev/null || true
  aws iam delete-role --role-name "$EBS_ROLE" 2>/dev/null || true
  log_ok "Deleted IAM role: $EBS_ROLE"
else
  log_info "IAM role not found: $EBS_ROLE (skipped)"
fi

# Clean temp files
rm -f "$TF_OUTPUTS"

echo ""
echo "============================================"
echo -e "  ${GREEN}Teardown complete!${NC}"
echo "  All AWS resources have been destroyed."
echo "  Estimated savings: ~\$12/day"
echo "============================================"
