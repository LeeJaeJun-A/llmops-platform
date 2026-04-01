#!/bin/bash
# Step 8: Helm deploy LLMOps application
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../shared" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/common.sh"
load_tf_outputs

log_step "Step 8/11: Helm deploy LLMOps app"

cd "$PROJECT_ROOT"

IMAGE_TAG="${IMAGE_TAG:-latest}"
DB_URL="${TF_DATABASE_URL:-}"
REDIS_URL="${TF_REDIS_URL:-}"

# Read secrets from .env.secrets if it exists
ANTHROPIC_KEY="" GEMINI_KEY="" API_KEYS_VAL=""
if [ -f ".env.secrets" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    key="${line%%=*}"; value="${line#*=}"
    value="${value#\"}"; value="${value%\"}"
    case "$key" in
      ANTHROPIC_API_KEY) ANTHROPIC_KEY="$value" ;;
      GEMINI_API_KEY)    GEMINI_KEY="$value" ;;
      API_KEYS)          API_KEYS_VAL="$value" ;;
    esac
  done < ".env.secrets"
fi

# Build helm dependencies
log_info "Building Helm dependencies..."
helm repo add bitnami https://charts.bitnami.com/bitnami > /dev/null 2>&1 || true
helm repo update > /dev/null 2>&1
helm dependency build "$HELM_CHART" > /dev/null 2>&1

# Escape commas in API_KEYS for helm --set-string
ESCAPED_API_KEYS=$(echo "$API_KEYS_VAL" | sed 's/,/\\,/g')

log_info "Installing Helm release..."
helm upgrade --install "$HELM_RELEASE" "$HELM_CHART" \
  -f "$HELM_VALUES" \
  --set "image.repository=${ECR_REPO}" \
  --set "image.tag=${IMAGE_TAG}" \
  --set "secrets.databaseUrl=${DB_URL}" \
  --set "secrets.redisUrl=${REDIS_URL}" \
  --set "secrets.anthropicApiKey=${ANTHROPIC_KEY}" \
  --set "secrets.geminiApiKey=${GEMINI_KEY}" \
  --set-string "secrets.apiKeys=${ESCAPED_API_KEYS}" \
  --set "config.observabilityBackend=noop" \
  --set "config.langfuseHost=http://langfuse-web.${LANGFUSE_NAMESPACE}.svc:3000" \
  --set "langfuse.enabled=false" \
  --set "postgresql.enabled=false" \
  --set "redis.enabled=false" \
  --set "karpenter.enabled=false" \
  --wait --timeout 5m > /dev/null 2>&1

# Apply Karpenter NodePool + EC2NodeClass
log_info "Applying Karpenter NodePool..."
cat <<EOF | kubectl apply -f - 2>/dev/null
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: ${CLUSTER_NAME}-general
spec:
  role: ${CLUSTER_NAME}-karpenter-node
  amiSelectorTerms:
    - alias: al2023@latest
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: ${CLUSTER_NAME}
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: ${CLUSTER_NAME}
  blockDeviceMappings:
    - deviceName: /dev/xvda
      ebs:
        volumeSize: 50Gi
        volumeType: gp3
        deleteOnTermination: true
        encrypted: true
  metadataOptions:
    httpEndpoint: enabled
    httpTokens: required
    httpPutResponseHopLimit: 2
EOF

cat <<EOF | kubectl apply -f - 2>/dev/null
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: ${CLUSTER_NAME}-general
spec:
  template:
    spec:
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: ${CLUSTER_NAME}-general
      requirements:
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["t3.medium", "t3.large", "m6i.large"]
        - key: kubernetes.io/arch
          operator: In
          values: ["amd64"]
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand"]
        - key: topology.kubernetes.io/zone
          operator: In
          values: ["${AWS_REGION}a", "${AWS_REGION}c"]
      expireAfter: 720h
  limits:
    cpu: 20
    memory: 40Gi
  disruption:
    consolidateAfter: 30s
    consolidationPolicy: WhenEmptyOrUnderutilized
EOF

log_ok "LLMOps app deployed (image: ${IMAGE_TAG})"
