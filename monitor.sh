#!/usr/bin/env bash
TOKEN="${DEYE_TOKEN:-}"
URL="${DEYE_URL:-https://eu1-developer.deyecloud.com/v1.0}"
DEVICE_SN="${DEYE_DEVICE_SN:-2509220055}"
LOG_WEBHOOK="${LOG_WEBHOOK:-}"

log() {
    local msg="[$(date +'%Y-%m-%d %H:%M:%S')] $1"
    echo "$msg"
    [[ -n "$LOG_WEBHOOK" ]] && curl -s -X POST -H "Content-Type: application/json" -d "{\"text\":\"$msg\"}" "$LOG_WEBHOOK" || true
}

if [[ -n "$TOKEN" ]]; then
    RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" "$URL/device/v1.0/currentData?deviceSn=$DEVICE_SN")
    VOLTAGE=$(echo "$RESPONSE" | jq -r '.dataList[] | select(.value | tonumber | . > 1000 and . < 3000) | .value' | head -1)
    FREQUENCY=$(echo "$RESPONSE" | jq -r '.dataList[] | select(.value | tonumber | . > 4000 and . < 6000) | .value' | head -1)
else
    log "TOKEN відсутній"
    VOLTAGE=FREQUENCY=
fi

if [[ -n "$VOLTAGE" && -n "$FREQUENCY" ]]; then
    log "Grid OK (V:$VOLTAGE Hz:$FREQUENCY)"
else
    log "Grid LOST — turn off socket"
    npx tuya-cli set --device-id "${{ secrets.TUYA_DEVICE_ID }}" \
      --access-id "${{ secrets.TUYA_ACCESS_ID }}" \
      --access-secret "${{ secrets.TUYA_ACCESS_SECRET }}" \
      --off || log "Tuya OFF failed"
fi
