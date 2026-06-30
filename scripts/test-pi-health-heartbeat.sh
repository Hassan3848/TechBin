#!/usr/bin/env bash
set -Eeuo pipefail

SUPABASE_URL="${VITE_SUPABASE_URL:-https://oqafmtuhfpapolylxvht.supabase.co}"
ORG_ID="${TECHBIN_ORG_ID:-techbin}"
BIN_CODE="${TECHBIN_BIN_CODE:-BIN-001}"
NOW="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

if [[ -z "${TECHBIN_DEVICE_TOKEN:-}" ]]; then
  printf 'TECHBIN_DEVICE_TOKEN is required.\n' >&2
  printf 'Generate a Pi token in the dashboard, then run:\n' >&2
  printf '  TECHBIN_DEVICE_TOKEN=tb_pi_... pnpm test:pi-health-heartbeat\n' >&2
  exit 1
fi

payload() {
  cat <<JSON
{
    "orgId": "${ORG_ID}",
    "binCode": "${BIN_CODE}",
    "lastSeen": "${NOW}",
    "hardwareHealth": {
      "frontUltrasonic": {"componentId":"front_ultrasonic","displayName":"Front ultrasonic","status":"healthy","faultCode":null,"message":"Valid ultrasonic observation received.","consecutiveFailures":0,"consecutiveSuccesses":3,"lastCheckedAt":"${NOW}","lastSuccessAt":"${NOW}"},
      "leftUltrasonic": {"componentId":"left_ultrasonic","displayName":"Left ultrasonic","status":"critical","faultCode":"echo_timeout","message":"No valid echo after configured retries.","consecutiveFailures":3,"consecutiveSuccesses":0,"lastCheckedAt":"${NOW}","lastSuccessAt":null},
      "rightUltrasonic": {"componentId":"right_ultrasonic","displayName":"Right ultrasonic","status":"healthy","faultCode":null,"message":"Valid ultrasonic observation received.","consecutiveFailures":0,"consecutiveSuccesses":2,"lastCheckedAt":"${NOW}","lastSuccessAt":"${NOW}"},
      "camera": {"componentId":"camera","displayName":"Camera","status":"healthy","faultCode":null,"message":"Camera capture/inference succeeded.","consecutiveFailures":0,"consecutiveSuccesses":1,"lastCheckedAt":"${NOW}","lastSuccessAt":"${NOW}"},
      "network": {"componentId":"network","displayName":"Network","status":"warning","faultCode":"network_request_failed","message":"offline","consecutiveFailures":1,"consecutiveSuccesses":0,"lastCheckedAt":"${NOW}","lastSuccessAt":null},
      "metalDetector": {"componentId":"metal_detector","displayName":"Metal detector","status":"disabled","faultCode":null,"message":"Metal detector override is intentionally disabled.","consecutiveFailures":0,"consecutiveSuccesses":0,"lastCheckedAt":"${NOW}","lastSuccessAt":null},
      "voiceFeedback": {"componentId":"voice_feedback","displayName":"Voice feedback","status":"disabled","faultCode":null,"message":"Voice feedback is intentionally disabled.","consecutiveFailures":0,"consecutiveSuccesses":0,"lastCheckedAt":"${NOW}","lastSuccessAt":null},
      "telemetryQueue": {"componentId":"telemetry_queue","displayName":"Telemetry queue","status":"warning","faultCode":"telemetry_queue_backlog_warning","message":"Telemetry queue has pending items.","consecutiveFailures":1,"consecutiveSuccesses":0,"lastCheckedAt":"${NOW}","lastSuccessAt":null}
    }
  }
JSON
}

curl -sS -X POST "$SUPABASE_URL/functions/v1/ingest-bin-state" \
  -H "x-device-token: $TECHBIN_DEVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(payload)"

printf '\n'
