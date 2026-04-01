#!/bin/bash
# Step 4: Install EBS CSI driver + gp3 StorageClass
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../shared" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/common.sh"

log_step "Step 4/11: EBS CSI driver + StorageClass"

EBS_ROLE_NAME="${CLUSTER_NAME}-ebs-csi"
OIDC_ISSUER=$(aws eks describe-cluster \
  --name "$CLUSTER_NAME" \
  --region "$AWS_REGION" \
  --query "cluster.identity.oidc.issuer" --output text | sed 's|https://||')

# Create IAM role (idempotent)
if aws iam get-role --role-name "$EBS_ROLE_NAME" >/dev/null 2>&1; then
  log_ok "EBS CSI IAM role exists"
else
  cat > /tmp/ebs-csi-trust.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::${AWS_ACCOUNT_ID}:oidc-provider/${OIDC_ISSUER}" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "${OIDC_ISSUER}:aud": "sts.amazonaws.com",
        "${OIDC_ISSUER}:sub": "system:serviceaccount:kube-system:ebs-csi-controller-sa"
      }
    }
  }]
}
EOF
  aws iam create-role \
    --role-name "$EBS_ROLE_NAME" \
    --assume-role-policy-document file:///tmp/ebs-csi-trust.json > /dev/null
  aws iam attach-role-policy \
    --role-name "$EBS_ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy
  log_ok "Created EBS CSI IAM role"
fi

# Install addon (idempotent)
ADDON_STATUS=$(aws eks describe-addon \
  --cluster-name "$CLUSTER_NAME" \
  --addon-name aws-ebs-csi-driver \
  --region "$AWS_REGION" \
  --query "addon.status" --output text 2>/dev/null || echo "NOT_FOUND")

if [ "$ADDON_STATUS" = "ACTIVE" ]; then
  log_ok "EBS CSI addon already active"
elif [ "$ADDON_STATUS" = "NOT_FOUND" ]; then
  aws eks create-addon \
    --cluster-name "$CLUSTER_NAME" \
    --addon-name aws-ebs-csi-driver \
    --service-account-role-arn "arn:aws:iam::${AWS_ACCOUNT_ID}:role/${EBS_ROLE_NAME}" \
    --region "$AWS_REGION" > /dev/null
  wait_for "EBS CSI addon active" \
    "[ \"\$(aws eks describe-addon --cluster-name $CLUSTER_NAME --addon-name aws-ebs-csi-driver --region $AWS_REGION --query 'addon.status' --output text 2>/dev/null)\" = 'ACTIVE' ]" \
    120
else
  log_info "EBS CSI addon status: $ADDON_STATUS — waiting..."
  wait_for "EBS CSI addon active" \
    "[ \"\$(aws eks describe-addon --cluster-name $CLUSTER_NAME --addon-name aws-ebs-csi-driver --region $AWS_REGION --query 'addon.status' --output text 2>/dev/null)\" = 'ACTIVE' ]" \
    120
fi

# Create gp3 StorageClass (idempotent)
if kubectl get storageclass gp3 >/dev/null 2>&1; then
  log_ok "gp3 StorageClass exists"
else
  kubectl apply -f - <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  fsType: ext4
volumeBindingMode: WaitForFirstConsumer
reclaimPolicy: Delete
allowVolumeExpansion: true
EOF
  log_ok "Created gp3 StorageClass"
fi
