#!/bin/bash
set -euo pipefail

THRESHOLD=80
LOGFILE="/var/log/wazuh_vd_cleanup.log"
MOUNT="/"

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

usage=$(df --output=pcent "$MOUNT" | tail -1 | tr -d ' %')
echo "$(timestamp) - Disk usage check: ${usage}%" >> "$LOGFILE"

if [ "$usage" -ge "$THRESHOLD" ]; then
    echo "$(timestamp) - Threshold (${THRESHOLD}%) exceeded, starting cleanup" >> "$LOGFILE"

    before_feed=$(du -sh /var/ossec/queue/vd/feed 2>/dev/null | cut -f1 || echo "N/A")
    before_tmp=$(du -sh /var/ossec/queue/vd_updater/tmp 2>/dev/null | cut -f1 || echo "N/A")
    echo "$(timestamp) - Before: vd/feed=${before_feed} vd_updater/tmp=${before_tmp}" >> "$LOGFILE"

    systemctl stop wazuh-manager
    sleep 2

    find /var/ossec/queue/vd/feed -mindepth 1 -delete
    find /var/ossec/queue/vd_updater/tmp -mindepth 1 -delete

    systemctl start wazuh-manager
    sleep 5

    if systemctl is-active --quiet wazuh-manager; then
        echo "$(timestamp) - wazuh-manager restarted OK" >> "$LOGFILE"
    else
        echo "$(timestamp) - !! WARNING: wazuh-manager NOT active after restart — manual check needed" >> "$LOGFILE"
    fi

    usage_after=$(df --output=pcent "$MOUNT" | tail -1 | tr -d ' %')
    echo "$(timestamp) - Disk usage after cleanup: ${usage_after}%" >> "$LOGFILE"
else
    echo "$(timestamp) - Under threshold, no action taken" >> "$LOGFILE"
fi
