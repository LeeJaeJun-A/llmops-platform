#!/bin/bash
# Step 6: Fix Karpenter IAM permissions (instance profiles + spot pricing)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../shared" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/common.sh"

log_step "Step 6/11: Karpenter IAM permission fix"

ROLE_NAME="${CLUSTER_NAME}-karpenter-controller"

aws iam put-role-policy \
  --role-name "$ROLE_NAME" \
  --policy-name karpenter-additional-permissions \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": [
        "iam:GetInstanceProfile",
        "iam:CreateInstanceProfile",
        "iam:DeleteInstanceProfile",
        "iam:TagInstanceProfile",
        "iam:AddRoleToInstanceProfile",
        "iam:RemoveRoleFromInstanceProfile",
        "ec2:DescribeSpotPriceHistory"
      ],
      "Resource": "*"
    }]
  }'

log_ok "Karpenter IAM permissions added"
