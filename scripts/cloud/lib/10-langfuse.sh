#!/bin/bash
# Step 10: Deploy Langfuse with AWS managed services (RDS, ElastiCache, S3)
# Only ClickHouse runs as a self-managed pod.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../shared" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/common.sh"
load_tf_outputs

log_step "Step 10/11: Langfuse deploy (managed services)"

# Validate required Terraform outputs
for var in TF_DB_HOST TF_DB_PORT TF_DB_USERNAME TF_DB_PASSWORD TF_REDIS_HOST TF_LANGFUSE_S3_BUCKET TF_LANGFUSE_S3_ACCESS_KEY TF_LANGFUSE_S3_SECRET_KEY; do
  if [ -z "${!var:-}" ]; then
    log_err "Missing Terraform output: ${var} — run step 02 first"
    exit 1
  fi
done

# Add Helm repo
helm repo add langfuse https://langfuse.github.io/langfuse-k8s > /dev/null 2>&1
helm repo update langfuse > /dev/null 2>&1

# --- Persist Langfuse secrets in AWS Secrets Manager ---
LANGFUSE_SM_NAME="${PROJECT_NAME}/${ENVIRONMENT}/langfuse"

# Try to load existing secrets, or generate new ones on first deploy
EXISTING_SECRETS=$(aws secretsmanager get-secret-value --secret-id "$LANGFUSE_SM_NAME" --region "$AWS_REGION" --query SecretString --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_SECRETS" ]; then
  SALT=$(echo "$EXISTING_SECRETS" | python3 -c "import sys,json; print(json.load(sys.stdin)['SALT'])")
  ENCRYPTION_KEY=$(echo "$EXISTING_SECRETS" | python3 -c "import sys,json; print(json.load(sys.stdin)['ENCRYPTION_KEY'])")
  NEXTAUTH_SECRET=$(echo "$EXISTING_SECRETS" | python3 -c "import sys,json; print(json.load(sys.stdin)['NEXTAUTH_SECRET'])")
  log_ok "Loaded Langfuse secrets from Secrets Manager"
else
  SALT=$(openssl rand -base64 32)
  ENCRYPTION_KEY=$(openssl rand -hex 32)
  NEXTAUTH_SECRET=$(openssl rand -base64 32)

  # Create or update the secret
  if aws secretsmanager describe-secret --secret-id "$LANGFUSE_SM_NAME" --region "$AWS_REGION" > /dev/null 2>&1; then
    aws secretsmanager put-secret-value --secret-id "$LANGFUSE_SM_NAME" --region "$AWS_REGION" \
      --secret-string "{\"SALT\":\"${SALT}\",\"ENCRYPTION_KEY\":\"${ENCRYPTION_KEY}\",\"NEXTAUTH_SECRET\":\"${NEXTAUTH_SECRET}\"}" > /dev/null
  else
    aws secretsmanager create-secret --name "$LANGFUSE_SM_NAME" --region "$AWS_REGION" \
      --secret-string "{\"SALT\":\"${SALT}\",\"ENCRYPTION_KEY\":\"${ENCRYPTION_KEY}\",\"NEXTAUTH_SECRET\":\"${NEXTAUTH_SECRET}\"}" > /dev/null
  fi
  log_ok "Generated and stored Langfuse secrets in Secrets Manager"
fi

# --- Create langfuse database on RDS if it doesn't exist ---
log_info "Ensuring langfuse database exists on RDS..."
kubectl run langfuse-db-init --rm -i --restart=Never \
  --image=postgres:17 \
  --env="PGPASSWORD=${TF_DB_PASSWORD}" \
  -- bash -c "
    psql -h '${TF_DB_HOST}' -U '${TF_DB_USERNAME}' -d postgres \
      -tc \"SELECT 1 FROM pg_database WHERE datname='langfuse'\" | grep -q 1 || \
    psql -h '${TF_DB_HOST}' -U '${TF_DB_USERNAME}' -d postgres \
      -c 'CREATE DATABASE langfuse'
  " > /dev/null 2>&1 || true
log_ok "Langfuse database ready"

# --- Deploy Langfuse with external services ---
log_info "Installing Langfuse (managed PostgreSQL, Redis, S3 + self-managed ClickHouse)..."
helm upgrade --install langfuse langfuse/langfuse \
  --namespace "$LANGFUSE_NAMESPACE" --create-namespace \
  --set "langfuse.salt.value=${SALT}" \
  --set "langfuse.encryptionKey.value=${ENCRYPTION_KEY}" \
  --set "langfuse.nextauth.secret.value=${NEXTAUTH_SECRET}" \
  --set "langfuse.nextauth.url=http://localhost:3000" \
  --set "postgresql.deploy=false" \
  --set "postgresql.host=${TF_DB_HOST}" \
  --set "postgresql.port=${TF_DB_PORT}" \
  --set "postgresql.auth.username=${TF_DB_USERNAME}" \
  --set "postgresql.auth.password=${TF_DB_PASSWORD}" \
  --set "postgresql.auth.database=langfuse" \
  --set "clickhouse.deploy=true" \
  --set "clickhouse.auth.password=langfuse-ch-pass" \
  --set "clickhouse.replicaCount=1" \
  --set "clickhouse.shards=1" \
  --set "clickhouse.zookeeper.replicaCount=1" \
  --set "redis.deploy=false" \
  --set "redis.host=${TF_REDIS_HOST}" \
  --set "redis.port=6379" \
  --set "redis.auth.enabled=false" \
  --set "s3.deploy=false" \
  --set "s3.bucket=${TF_LANGFUSE_S3_BUCKET}" \
  --set "s3.region=${AWS_REGION}" \
  --set "s3.endpoint=https://s3.${AWS_REGION}.amazonaws.com" \
  --set "s3.forcePathStyle=false" \
  --set "s3.accessKeyId.value=${TF_LANGFUSE_S3_ACCESS_KEY}" \
  --set "s3.secretAccessKey.value=${TF_LANGFUSE_S3_SECRET_KEY}" \
  --timeout 10m > /dev/null 2>&1

# --- Wait for ClickHouse (only self-managed pod) ---
CH_STATUS=$(kubectl get pods -n "$LANGFUSE_NAMESPACE" -l app.kubernetes.io/component=clickhouse --no-headers 2>/dev/null | head -1 | awk '{print $3}')
if [ "$CH_STATUS" = "Pending" ]; then
  log_warn "ClickHouse pending — scaling up node group..."
  CURRENT_DESIRED=$(aws eks describe-nodegroup --cluster-name "$CLUSTER_NAME" --nodegroup-name "${CLUSTER_NAME}-system" --region "$AWS_REGION" --query "nodegroup.scalingConfig.desiredSize" --output text 2>/dev/null || echo "2")
  NEW_DESIRED=$((CURRENT_DESIRED + 1))
  aws eks update-nodegroup-config \
    --cluster-name "$CLUSTER_NAME" \
    --nodegroup-name "${CLUSTER_NAME}-system" \
    --scaling-config "minSize=2,maxSize=5,desiredSize=${NEW_DESIRED}" \
    --region "$AWS_REGION" > /dev/null 2>&1
  log_info "Scaled to $NEW_DESIRED nodes, waiting..."
fi

wait_for "ClickHouse running" \
  "kubectl get pods -n $LANGFUSE_NAMESPACE -l app.kubernetes.io/component=clickhouse --no-headers 2>/dev/null | grep -q Running" \
  300

# --- Wait for Langfuse web ---
wait_for "Langfuse web running" \
  "kubectl get pods -n $LANGFUSE_NAMESPACE -l app=web --no-headers 2>/dev/null | grep -q '1/1.*Running'" \
  300

# --- Create Langfuse admin account ---
log_info "Creating Langfuse admin account..."
kubectl port-forward svc/langfuse-web 3000:3000 -n "$LANGFUSE_NAMESPACE" > /dev/null 2>&1 &
PF_PID=$!
sleep 5

LANGFUSE_ADMIN_EMAIL="${LANGFUSE_ADMIN_EMAIL:-admin@llmops.dev}"
LANGFUSE_ADMIN_PASS="${LANGFUSE_ADMIN_PASS:-$(openssl rand -base64 16)}"

SIGNUP_RESULT=$(curl -s -X POST http://localhost:3000/api/auth/signup \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"admin\",\"email\":\"${LANGFUSE_ADMIN_EMAIL}\",\"password\":\"${LANGFUSE_ADMIN_PASS}\"}" 2>/dev/null || echo '{"error":"failed"}')

kill $PF_PID 2>/dev/null || true

if echo "$SIGNUP_RESULT" | grep -q "User created\|already exists"; then
  log_ok "Langfuse account ready (${LANGFUSE_ADMIN_EMAIL})"
  log_warn "Password: ${LANGFUSE_ADMIN_PASS} — save this now, it won't be shown again"
else
  log_warn "Could not create account — create manually at http://localhost:3000"
fi

log_ok "Langfuse deployed (managed: RDS, ElastiCache, S3 | pod: ClickHouse)"
echo ""
log_warn "MANUAL STEP REQUIRED:"
log_info "1. Run: kubectl port-forward svc/langfuse-web 3000:3000 -n ${LANGFUSE_NAMESPACE}"
log_info "2. Open http://localhost:3000 → Login with credentials shown above"
log_info "3. Create project → Settings → API Keys → Copy public + secret key"
log_info "4. Add keys to .env.secrets and run: ./scripts/shared/upload-secrets.sh"
log_info "5. Then run: helm upgrade llmops helm/llmops-platform/ --reuse-values \\"
log_info "     --set secrets.langfusePublicKey=pk-... \\"
log_info "     --set secrets.langfuseSecretKey=sk-... \\"
log_info "     --set config.observabilityBackend=langfuse"
