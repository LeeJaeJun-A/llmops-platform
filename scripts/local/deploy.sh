#!/bin/bash
# =============================================================================
# LLMOps Platform — Local Docker Compose Deploy
# One-click: starts all services, runs migrations, verifies
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../shared/config.sh"
source "${SCRIPT_DIR}/../shared/common.sh"

cd "$PROJECT_ROOT"

echo ""
echo "============================================"
echo "  LLMOps Platform — Local Deploy"
echo "  Mode: Docker Compose"
echo "============================================"
echo ""

# Pre-flight checks
log_step "Pre-flight checks"
require_cmd docker python3

if ! docker info >/dev/null 2>&1; then
  log_err "Docker is not running"
  exit 1
fi
log_ok "Docker running"

# Check port conflicts
for port in 5432 6379 8000 3000; do
  if lsof -i ":${port}" -sTCP:LISTEN >/dev/null 2>&1; then
    PROC=$(lsof -i ":${port}" -sTCP:LISTEN | tail -1 | awk '{print $1}')
    log_err "Port ${port} already in use by ${PROC}"
    log_info "Stop it first, then retry"
    exit 1
  fi
done
log_ok "Required ports available (5432, 6379, 8000, 3000)"

# Check for .env — create from example if missing
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    log_warn "Created .env from .env.example — edit if needed"
  else
    log_err ".env not found and no .env.example to copy from"
    exit 1
  fi
fi
log_ok ".env found"

# Check for .env.secrets
if [ -f ".env.secrets" ]; then
  log_ok ".env.secrets found"
else
  log_warn "No .env.secrets found — API keys may be empty"
  log_info "Create from template: cp .env.secrets.example .env.secrets"
fi

echo ""

# Step 1: Build and start services
log_step "Step 1/4: Docker Compose up"
log_info "Building and starting all services..."
docker compose up -d --build 2>&1 | tail -3
log_ok "Services starting"

# Step 2: Wait for health
log_step "Step 2/4: Wait for services"

wait_for "PostgreSQL" \
  "docker compose exec -T llmops-postgres pg_isready -U llmops" \
  60 5

wait_for "Redis" \
  "docker compose exec -T redis redis-cli ping" \
  30 5

wait_for "LLMOps app" \
  "curl -sf http://localhost:8000/healthz" \
  60 5

# Step 3: Run migrations
log_step "Step 3/4: Database migrations"

docker compose exec -T llmops alembic upgrade head 2>/dev/null

TABLE_COUNT=$(docker compose exec -T llmops python3 -c "
import asyncio
from sqlalchemy import text
from llmops.db.session import engine

async def check():
    async with engine.connect() as conn:
        result = await conn.execute(text(\"SELECT count(*) FROM pg_tables WHERE schemaname='public'\"))
        print(result.scalar())
    await engine.dispose()

asyncio.run(check())
" 2>/dev/null)

log_ok "Migrations complete — $TABLE_COUNT tables"

# Step 4: Verify
log_step "Step 4/4: Verify"

PASS=0 FAIL=0

check() {
  local name="$1" result="$2" expect="$3"
  if echo "$result" | grep -q "$expect"; then
    log_ok "$name"
    PASS=$((PASS + 1))
  else
    log_err "$name"
    FAIL=$((FAIL + 1))
  fi
}

R=$(curl -s http://localhost:8000/healthz 2>/dev/null)
check "Health check" "$R" '"status":"ok"'

R=$(curl -s http://localhost:8000/readyz 2>/dev/null)
check "Readiness" "$R" '"postgresql":"ok"'

LOCAL_API_KEY=$(grep "^API_KEYS=" .env.secrets .env 2>/dev/null | head -1 | cut -d: -f2- | cut -d= -f2- | cut -d, -f1)
R=$(curl -s http://localhost:8000/v1/scoring/strategies -H "Authorization: Bearer ${LOCAL_API_KEY}" 2>/dev/null)
check "Scoring strategies" "$R" '"rule_based"'

# Test LLM completion only if API key is set
ANTHROPIC_KEY=$(grep "^ANTHROPIC_API_KEY=" .env.secrets .env 2>/dev/null | head -1 | cut -d: -f2- | cut -d= -f2-)
if [ -n "$ANTHROPIC_KEY" ] && [ "$ANTHROPIC_KEY" != "your-anthropic-api-key" ]; then
  R=$(curl -s -X POST http://localhost:8000/v1/chat/completions \
    -H "Authorization: Bearer ${LOCAL_API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{"model":"claude-sonnet-4-20250514","messages":[{"role":"user","content":"Say hi"}],"max_tokens":20}' 2>/dev/null)
  check "Anthropic completion" "$R" '"role":"assistant"'
else
  log_warn "Anthropic: skipped (no API key)"
fi

GEMINI_KEY=$(grep "^GEMINI_API_KEY=" .env.secrets .env 2>/dev/null | head -1 | cut -d: -f2- | cut -d= -f2-)
if [ -n "$GEMINI_KEY" ] && [ "$GEMINI_KEY" != "your-gemini-api-key" ]; then
  R=$(curl -s -X POST http://localhost:8000/v1/chat/completions \
    -H "Authorization: Bearer ${LOCAL_API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{"model":"gemini-2.5-flash","messages":[{"role":"user","content":"Say hi"}],"max_tokens":50}' 2>/dev/null)
  check "Gemini completion" "$R" '"model":"gemini'
else
  log_warn "Gemini: skipped (no API key)"
fi

echo ""
echo "============================================"
echo -e "  ${GREEN}Local deploy complete!${NC}"
echo "  Results: ${PASS} passed, ${FAIL} failed"
echo ""
echo "  App:      http://localhost:8000"
echo "  Docs:     http://localhost:8000/docs"
echo "  Langfuse: http://localhost:3000 (wait ~2 min)"
echo ""
echo "  Stop: make local-down"
echo "  Logs: make local-logs"
echo "============================================"
