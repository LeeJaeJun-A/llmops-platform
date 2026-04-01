#!/bin/bash
# Step 1: Create S3 bucket + DynamoDB table for Terraform state
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../shared" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/common.sh"

log_step "Step 1/11: State infrastructure (S3 + DynamoDB)"

# S3 bucket
if aws s3api head-bucket --bucket "$STATE_BUCKET" --region "$AWS_REGION" 2>/dev/null; then
  log_ok "S3 bucket exists: $STATE_BUCKET"
else
  aws s3 mb "s3://${STATE_BUCKET}" --region "$AWS_REGION" > /dev/null
  aws s3api put-bucket-versioning \
    --bucket "$STATE_BUCKET" \
    --versioning-configuration Status=Enabled \
    --region "$AWS_REGION"
  log_ok "Created S3 bucket: $STATE_BUCKET"
fi

# DynamoDB table
if aws dynamodb describe-table --table-name "$LOCK_TABLE" --region "$AWS_REGION" >/dev/null 2>&1; then
  log_ok "DynamoDB table exists: $LOCK_TABLE"
else
  aws dynamodb create-table \
    --table-name "$LOCK_TABLE" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "$AWS_REGION" > /dev/null
  log_ok "Created DynamoDB table: $LOCK_TABLE"
fi
