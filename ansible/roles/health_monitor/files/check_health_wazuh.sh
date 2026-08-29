#!/bin/bash
# health-monitor: sadece durum degisikliginde veya heartbeat suresi dolunca loglar
SERVICES="wazuh-manager wazuh-indexer wazuh-dashboard auditd filebeat clickdetect docker"
STATE_FILE="/opt/health-monitor/state.json"
LOG_FILE="/var/log/health-monitor/health.json"
HEARTBEAT_SEC=900

[ -f "$STATE_FILE" ] || echo '{}' | sudo tee "$STATE_FILE" > /dev/null

now=$(date +%s)
now_iso=$(date -u +%Y-%m-%dT%H:%M:%SZ)
HOST="wazuh-server"

for svc in $SERVICES; do
  status=$(systemctl is-active "$svc" 2>/dev/null); [ -z "$status" ] && status="not-found"
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
done

# --- Kaynak esigi kontrolleri (disk/bellek/yuk) ---
DISK_WARN=85
DISK_CRIT=95
MEM_WARN=90
MEM_CRIT=95
LOAD_WARN_MULT=1
LOAD_CRIT_MULT=2

check_resource() {
  local name="$1" value="$2" warn="$3" crit="$4"
  local level="ok"
  if awk "BEGIN{exit !($value >= $crit)}"; then level="critical"
  elif awk "BEGIN{exit !($value >= $warn)}"; then level="warning"
  fi

  local prev_level=$(jq -r --arg s "res_$name" '.[$s].status // "unknown"' "$STATE_FILE")
  local prev_ts=$(jq -r --arg s "res_$name" '.[$s].last_logged // 0' "$STATE_FILE")
  local elapsed=$((now - prev_ts))

  if [ "$level" != "$prev_level" ] || [ "$elapsed" -ge "$HEARTBEAT_SEC" ]; then
    local event="heartbeat"
    [ "$level" != "$prev_level" ] && event="state_change"
    echo "{\"timestamp\":\"$now_iso\",\"host\":\"$HOST\",\"check_kind\":\"resource\",\"res_name\":\"$name\",\"svc_status\":\"$level\",\"res_value\":\"$value\",\"event\":\"$event\"}" >> "$LOG_FILE"
    local tmp=$(jq --arg s "res_$name" --arg st "$level" --argjson ts "$now" '.[$s] = {status: $st, last_logged: $ts}' "$STATE_FILE")
    echo "$tmp" | sudo tee "$STATE_FILE" > /dev/null
  fi
}

disk_pct=$(df / --output=pcent | tail -1 | tr -dc '0-9')
check_resource "disk_root" "$disk_pct" "$DISK_WARN" "$DISK_CRIT"

mem_total=$(free -m | awk '/^Mem:/{print $2}')
mem_avail=$(free -m | awk '/^Mem:/{print $7}')
mem_pct=$(( (mem_total - mem_avail) * 100 / mem_total ))
check_resource "memory" "$mem_pct" "$MEM_WARN" "$MEM_CRIT"

cores=$(nproc)
load1=$(awk '{print $1}' /proc/loadavg)
load_ratio=$(awk "BEGIN{printf \"%.2f\", $load1/$cores}")
check_resource "load_avg" "$load_ratio" "$LOAD_WARN_MULT" "$LOAD_CRIT_MULT"
