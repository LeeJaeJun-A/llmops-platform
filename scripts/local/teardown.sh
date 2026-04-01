#!/bin/bash
# =============================================================================
# LLMOps Platform — Local Docker Compose Teardown
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../shared/config.sh"
source "${SCRIPT_DIR}/../shared/common.sh"

cd "$PROJECT_ROOT"

echo ""
echo "============================================"
echo "  LLMOps Platform — Local Teardown"
echo "============================================"
echo ""

KEEP_DATA=false
if [ "${1:-}" = "--keep-data" ]; then
  KEEP_DATA=true
fi

log_step "Stopping containers"
docker compose down 2>/dev/null
log_ok "Containers stopped"

if [ "$KEEP_DATA" = false ]; then
  log_step "Removing volumes"
  docker compose down -v 2>/dev/null
  log_ok "Volumes removed"
else
  log_info "Volumes preserved (--keep-data)"
fi

echo ""
echo "============================================"
echo -e "  ${GREEN}Local teardown complete!${NC}"
if [ "$KEEP_DATA" = true ]; then
  echo "  Data preserved. Run without --keep-data to remove volumes."
fi
echo "============================================"
