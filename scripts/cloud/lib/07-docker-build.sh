#!/bin/bash
# Step 7: Build Docker image and push to ECR
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../shared" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/common.sh"

log_step "Step 7/11: Docker build + ECR push"

cd "$PROJECT_ROOT"

IMAGE_TAG=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")

# Create ECR repo (idempotent)
if aws ecr describe-repositories --repository-names "${PROJECT_NAME}-platform" --region "$AWS_REGION" >/dev/null 2>&1; then
  log_ok "ECR repository exists"
else
  aws ecr create-repository \
    --repository-name "${PROJECT_NAME}-platform" \
    --region "$AWS_REGION" > /dev/null
  log_ok "Created ECR repository"
fi

# Login to ECR
aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin \
  "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com" > /dev/null 2>&1

# Build
log_info "Building image (linux/amd64)..."
docker build --platform linux/amd64 \
  -t "${ECR_REPO}:${IMAGE_TAG}" \
  -t "${ECR_REPO}:latest" \
  . > /dev/null 2>&1

# Push
log_info "Pushing to ECR..."
docker push "${ECR_REPO}:${IMAGE_TAG}" > /dev/null 2>&1
docker push "${ECR_REPO}:latest" > /dev/null 2>&1

log_ok "Image pushed: ${ECR_REPO}:${IMAGE_TAG}"

# Save tag for helm
save_tf_output "IMAGE_TAG" "$IMAGE_TAG"
