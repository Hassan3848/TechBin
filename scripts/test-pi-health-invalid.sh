#!/usr/bin/env bash
set -Eeuo pipefail

SUPABASE_URL="${VITE_SUPABASE_URL:-https://oqafmtuhfpapolylxvht.supabase.co}"
ORG_ID="${TECHBIN_ORG_ID:-techbin}"
BIN_CODE="${TECHBIN_BIN_CODE:-BIN-001}"
NOW="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

if [[ -z "${TECHBIN_DEVICE_TOKEN:-}" ]]; then
  printf 'TECHBIN_DEVICE_TOKEN is required.\n' >&2
  printf 'Generate a Pi token in the dashboard, then run:\n' >&2
  printf '  TECHBIN_DEVICE_TOKEN=tb_pi_... pnpm test:pi-health-invalid\n' >&2
  exit 1
fi

curl -sS -X POST "$SUPABASE_URL/functions/v1/ingest-bin-state" \
  -H "x-device-token: $TECHBIN_DEVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"orgId\": \"$ORG_ID\",
    \"binCode\": \"$BIN_CODE\",
    \"lastSeen\": \"$NOW\",
    \"hardwareHealth\": {
      \"frontUltrasonic\": {\"componentId\":\"front_ultrasonic\",\"displayName\":\"Front ultrasonic\",\"status\":\"broken\",\"faultCode\":null,\"message\":\"Invalid status test.\",\"consecutiveFailures\":0,\"consecutiveSuccesses\":0,\"lastCheckedAt\":\"$NOW\",\"lastSuccessAt\":null}
    }
  }"

printf '\n'
