#!/bin/bash
# Step 11: Verify deployment with E2E smoke tests
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../shared" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/common.sh"

log_step "Step 11/11: Verify deployment"

# Read API key from .env.secrets
AUTH_KEY=""
if [ -f "${PROJECT_ROOT}/.env.secrets" ]; then
  KEY_LINE=$(grep "^API_KEYS=" "${PROJECT_ROOT}/.env.secrets" 2>/dev/null || echo "")
  if [ -n "$KEY_LINE" ]; then
    AUTH_KEY=$(echo "${KEY_LINE#API_KEYS=}" | cut -d, -f1 | tr -d '"' | tr -d "'")
  fi
fi
if [ -z "$AUTH_KEY" ]; then
  log_err "No API key found. Set API_KEYS in .env.secrets"
  exit 1
fi

# Port-forward
kill $(lsof -ti:8000) 2>/dev/null || true
sleep 1
kubectl port-forward svc/${HELM_RELEASE}-llmops-platform 8000:8000 > /dev/null 2>&1 &
PF_PID=$!
sleep 4

PASS=0 FAIL=0
AUTH="Authorization: Bearer ${AUTH_KEY}"

check() {
  local name="$1" result="$2" expect="$3"
  if echo "$result" | grep -q "$expect"; then
    log_ok "$name"
    PASS=$((PASS + 1))
  else
    log_err "$name"
    log_info "  Expected: $expect"
    log_info "  Got: $(echo "$result" | head -1 | cut -c1-100)"
    FAIL=$((FAIL + 1))
  fi
}

# Tests
R=$(curl -s http://localhost:8000/healthz 2>/dev/null)
check "Health check" "$R" '"status":"ok"'

R=$(curl -s http://localhost:8000/readyz 2>/dev/null)
check "Readiness check" "$R" '"status":"ready"'

R=$(curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"model":"claude-sonnet-4-20250514","messages":[{"role":"user","content":"Say hi"}],"max_tokens":50}' 2>/dev/null)
check "Anthropic completion" "$R" '"role":"assistant"'

R=$(curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"model":"gemini-2.5-flash","messages":[{"role":"user","content":"Say hi"}],"max_tokens":100}' 2>/dev/null)
check "Gemini completion" "$R" '"model":"gemini'

R=$(curl -s http://localhost:8000/v1/scoring/strategies -H "$AUTH" 2>/dev/null)
check "Scoring strategies" "$R" '"rule_based"'

R=$(curl -s http://localhost:8000/v1/scoring/strategies -H "Authorization: Bearer wrong-key" 2>/dev/null)
check "Auth rejection" "$R" '"Invalid API key"'

# Cleanup
kill $PF_PID 2>/dev/null || true

echo ""
echo "============================================"
echo -e "  Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
