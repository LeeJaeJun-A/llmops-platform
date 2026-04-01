#!/bin/bash
# Step 2: Terragrunt apply all modules in dependency order
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../shared" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/common.sh"

log_step "Step 2/11: Terraform apply (this takes 10-20 minutes)"

cd "${PROJECT_ROOT}/${TF_DIR}"

# Clear previous outputs
> "$TF_OUTPUTS"

apply_module() {
  local module="$1"
  log_info "Applying ${module}..."
  cd "${PROJECT_ROOT}/${TF_DIR}/${module}"
  terragrunt init -input=false > /dev/null 2>&1
  local output
  output=$(terragrunt apply -auto-approve -input=false 2>&1) || {
    echo "$output" | tail -20
    log_err "Failed to apply ${module}"
    return 1
  }
  echo "$output" | tail -3
  log_ok "$module"
  cd "${PROJECT_ROOT}/${TF_DIR}"
}

# Phase 1: Networking (no deps)
apply_module "networking"

# Phase 2: Kubernetes (depends on networking) — slowest, ~10 min
apply_module "kubernetes"

# Phase 3: Database, Redis, Storage (depend on networking, can run after k8s)
apply_module "database"
apply_module "redis"
apply_module "storage"

# Phase 4: Karpenter (depends on networking + kubernetes)
apply_module "karpenter"

# Phase 5: Secrets (depends on database + redis)
apply_module "secrets"

# Save key outputs
log_info "Saving Terraform outputs..."

cd "${PROJECT_ROOT}/${TF_DIR}/database"
DB_URL=$(terragrunt output -raw database_url 2>/dev/null)
DB_HOST=$(terragrunt output -raw host 2>/dev/null)
DB_PORT=$(terragrunt output -raw port 2>/dev/null)
DB_USERNAME=$(terragrunt output -raw username 2>/dev/null)
DB_PASSWORD=$(terragrunt output -raw password 2>/dev/null)
save_tf_output "TF_DATABASE_URL" "$DB_URL"
save_tf_output "TF_DB_HOST" "$DB_HOST"
save_tf_output "TF_DB_PORT" "$DB_PORT"
save_tf_output "TF_DB_USERNAME" "$DB_USERNAME"
save_tf_output "TF_DB_PASSWORD" "$DB_PASSWORD"

cd "${PROJECT_ROOT}/${TF_DIR}/redis"
REDIS_URL=$(terragrunt output -raw redis_url 2>/dev/null)
REDIS_HOST=$(terragrunt output -raw endpoint 2>/dev/null)
save_tf_output "TF_REDIS_URL" "$REDIS_URL"
save_tf_output "TF_REDIS_HOST" "$REDIS_HOST"

cd "${PROJECT_ROOT}/${TF_DIR}/storage"
S3_BUCKET=$(terragrunt output -raw langfuse_bucket_name 2>/dev/null)
S3_ACCESS_KEY=$(terragrunt output -raw langfuse_s3_access_key_id 2>/dev/null)
S3_SECRET_KEY=$(terragrunt output -raw langfuse_s3_secret_access_key 2>/dev/null)
save_tf_output "TF_LANGFUSE_S3_BUCKET" "$S3_BUCKET"
save_tf_output "TF_LANGFUSE_S3_ACCESS_KEY" "$S3_ACCESS_KEY"
save_tf_output "TF_LANGFUSE_S3_SECRET_KEY" "$S3_SECRET_KEY"

cd "${PROJECT_ROOT}/${TF_DIR}/kubernetes"
CLUSTER_ENDPOINT=$(terragrunt output -raw cluster_endpoint 2>/dev/null)
OIDC_ARN=$(terragrunt output -raw oidc_provider_arn 2>/dev/null)
save_tf_output "TF_CLUSTER_ENDPOINT" "$CLUSTER_ENDPOINT"
save_tf_output "TF_OIDC_ARN" "$OIDC_ARN"

cd "${PROJECT_ROOT}/${TF_DIR}/karpenter"
KARPENTER_ROLE=$(terragrunt output -raw controller_role_arn 2>/dev/null)
save_tf_output "TF_KARPENTER_ROLE_ARN" "$KARPENTER_ROLE"

log_ok "All Terraform modules applied"
