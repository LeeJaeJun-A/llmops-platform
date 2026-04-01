#!/bin/bash
# Upload .env.secrets to AWS Secrets Manager (merges with existing secret)
# Usage: ./scripts/upload_secrets.sh [env-file] [secret-name] [region]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"
source "${SCRIPT_DIR}/common.sh"

ENV_FILE="${1:-.env.secrets}"
SECRET_NAME="${2:-${PROJECT_NAME}/${ENVIRONMENT}/app}"
REGION="${3:-${AWS_REGION}}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found"
  echo ""
  echo "Usage: $0 [env-file] [secret-name] [region]"
  echo ""
  echo "Create from template:"
  echo "  cp .env.secrets.example .env.secrets"
  echo "  # Fill in your API keys"
  echo "  $0"
  exit 1
fi

# Parse .env file into JSON using Python (handles escaping properly)
NEW_JSON=$(python3 -c "
import json, sys

result = {}
with open('$ENV_FILE') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip().strip('\"').strip(\"'\")
        if not key:
            continue
        result[key] = value

# Warn about empty values
empty = [k for k, v in result.items() if not v]
if empty:
    print(f'WARNING: Empty values for: {', '.join(empty)}', file=sys.stderr)

print(json.dumps(result))
")

# Validate we have at least one non-empty key
NON_EMPTY=$(echo "$NEW_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(sum(1 for v in data.values() if v))
")

if [ "$NON_EMPTY" -eq 0 ]; then
  echo "Error: All values are empty in $ENV_FILE. Nothing to upload."
  exit 1
fi

echo "Reading secrets from: $ENV_FILE"
echo "Target: $SECRET_NAME ($REGION)"

# Merge with existing secret (preserve DATABASE_URL, REDIS_URL from Terraform)
MERGED_JSON="$NEW_JSON"
if aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "Merging with existing secret..."
  EXISTING=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_NAME" \
    --region "$REGION" \
    --query "SecretString" --output text 2>/dev/null || echo "{}")

  MERGED_JSON=$(python3 -c "
import json, sys
existing = json.loads('$EXISTING') if '$EXISTING' else {}
new = json.loads(sys.stdin.read())
# Merge: new values overwrite existing, but keep existing keys not in new
existing.update({k: v for k, v in new.items() if v})  # only overwrite with non-empty
print(json.dumps(existing))
" <<< "$NEW_JSON")

  # Write to temp file (avoids secret in ps output)
  TMPFILE=$(mktemp)
  trap "rm -f $TMPFILE" EXIT
  echo "$MERGED_JSON" > "$TMPFILE"

  aws secretsmanager put-secret-value \
    --secret-id "$SECRET_NAME" \
    --secret-string "file://$TMPFILE" \
    --region "$REGION" > /dev/null
else
  echo "Creating new secret..."
  TMPFILE=$(mktemp)
  trap "rm -f $TMPFILE" EXIT
  echo "$MERGED_JSON" > "$TMPFILE"

  aws secretsmanager create-secret \
    --name "$SECRET_NAME" \
    --secret-string "file://$TMPFILE" \
    --region "$REGION" > /dev/null
fi

echo ""
echo "Done! Secrets uploaded to $SECRET_NAME"
echo "Keys uploaded:"
echo "$NEW_JSON" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for k, v in data.items():
    status = 'set' if v else 'empty (skipped)'
    print(f'  - {k}: {status}')
"
