#!/bin/bash
FORTIGATE_IP="10.0.0.X"  # FortiGate'in VCN ici IP'si
HOST="fortigate-appliance"
STATE_FILE="/opt/health-monitor/state.json"
LOG_FILE="/var/log/health-monitor/health.json"
HEARTBEAT_SEC=900

[ -f "$STATE_FILE" ] || echo '{}' | sudo tee "$STATE_FILE" > /dev/null

now=$(date +%s)
now_iso=$(date -u +%Y-%m-%dT%H:%M:%SZ)

if ping -c 2 -W 3 "$FORTIGATE_IP" > /dev/null 2>&1; then
  status="active"
else
  status="inactive"
fi

svc="wan_reachability"
prev_status=$(jq -r --arg s "$svc" '.[$s].status // "unknown"' "$STATE_FILE")
prev_ts=$(jq -r --arg s "$svc" '.[$s].last_logged // 0' "$STATE_FILE")
elapsed=$((now - prev_ts))

if [ "$status" != "$prev_status" ] || [ "$elapsed" -ge "$HEARTBEAT_SEC" ]; then
  event="heartbeat"
  [ "$status" != "$prev_status" ] && event="state_change"
  echo "{\"timestamp\":\"$now_iso\",\"host\":\"$HOST\",\"service\":\"$svc\",\"svc_status\":\"$status\",\"event\":\"$event\"}" >> "$LOG_FILE"
  tmp=$(jq --arg s "$svc" --arg st "$status" --argjson ts "$now" '.[$s] = {status: $st, last_logged: $ts}' "$STATE_FILE")
  echo "$tmp" | sudo tee "$STATE_FILE" > /dev/null
fi
