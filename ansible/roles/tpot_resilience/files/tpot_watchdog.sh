#!/usr/bin/env bash
# tpot.service "failed" durumuna düşerse syslog'a kritik seviyede bir satır yazar
# (Wazuh agent tarafından toplanması bekleniyor). Otomatik restart DENEMEZ -
# bilinçli olarak: kalıcı bir sorunu (örn. uzun süreli ağ kesintisi) sonsuz
# döngüye sokmamak için, insan/Wazuh müdahalesi bekler.
set -euo pipefail

if ! systemctl is-active --quiet tpot.service; then
  running=$(docker ps --filter status=running -q 2>/dev/null | wc -l || echo "?")
  state=$(systemctl is-active tpot.service 2>/dev/null || echo "unknown")
  logger -p daemon.crit -t tpot-watchdog \
    "ALERT: tpot.service is not active (state=${state}, running_containers=${running}). Manual check needed: systemctl status tpot ; systemctl reset-failed tpot && systemctl start tpot"
fi
