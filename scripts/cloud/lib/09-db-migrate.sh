#!/bin/bash
# Step 9: Run database migrations via kubectl exec
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../shared" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/common.sh"

log_step "Step 9/11: Database migrations"

# Wait for app pod to be running
wait_for "app pod running" \
  "kubectl get pods -l app.kubernetes.io/component=api --no-headers 2>/dev/null | grep -q Running" \
  120

APP_POD=$(kubectl get pods -l app.kubernetes.io/component=api -o jsonpath='{.items[0].metadata.name}')

log_info "Running migrations on pod: $APP_POD"

kubectl exec "$APP_POD" -- alembic upgrade head 2>/dev/null

# Verify
TABLE_COUNT=$(kubectl exec "$APP_POD" -- python3 -c "
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
