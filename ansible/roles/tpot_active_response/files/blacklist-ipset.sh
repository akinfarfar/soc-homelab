#!/bin/bash
# Wazuh Active Response - T-Pot saldirganini ipset blacklist'e ekle/cikar

LOCAL=$(dirname "$0")
cd "$LOCAL/../.." || exit 1
LOG_FILE="$(pwd)/logs/active-responses.log"

read -r INPUT_JSON

COMMAND=$(echo "$INPUT_JSON" | jq -r '.command')
SRCIP=$(echo "$INPUT_JSON" | jq -r '
  .parameters.alert.data.srcip //
  .parameters.alert.data.src_ip //
  .parameters.alert.srcip //
  empty')

if [ -z "$SRCIP" ] || [ "$SRCIP" = "null" ]; then
  echo "$(date '+%Y/%m/%d %H:%M:%S') blacklist-ipset.sh: srcip bulunamadi - $INPUT_JSON" >> "$LOG_FILE"
  exit 1
fi

case "$COMMAND" in
  add)
    ipset add blacklist-ar "$SRCIP" -exist
    echo "$(date '+%Y/%m/%d %H:%M:%S') blacklist-ipset.sh: ADD $SRCIP" >> "$LOG_FILE"
    ;;
  delete)
    ipset del blacklist-ar "$SRCIP" -exist
    echo "$(date '+%Y/%m/%d %H:%M:%S') blacklist-ipset.sh: DELETE $SRCIP" >> "$LOG_FILE"
    ;;
  *)
    echo "$(date '+%Y/%m/%d %H:%M:%S') blacklist-ipset.sh: bilinmeyen komut '$COMMAND'" >> "$LOG_FILE"
    exit 1
    ;;
esac
exit 0
