#!/bin/bash
set -uo pipefail

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

command -v ipset >/dev/null 2>&1 || { echo "$(date): HATA - ipset bulunamadi, PATH kontrol et" >&2; exit 1; }

export SOPS_AGE_KEY_FILE=/etc/sops/age/keys.txt
SOPS_BIN=/usr/local/bin/sops
SECRETS_FILE=/home/ubuntu/soc-secrets/secrets/tpot/abuseipdb.yaml

APIKEY=$("$SOPS_BIN" --decrypt --extract '["abuseipdb_api_key"]' "$SECRETS_FILE")
if [ -z "$APIKEY" ]; then
  echo "$(date): HATA - APIKEY sops'tan cozulemedi, script durduruldu" >&2
  exit 1
fi

TMPSET="blacklist_tmp"
MAINSET="blacklist-feed"

is_ipv4() {
  [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?$ ]]
}

ipset create $TMPSET hash:net family inet hashsize 4096 maxelem 200000 timeout 0 -exist
ipset flush $TMPSET

curl -s -G "https://api.abuseipdb.com/api/v2/blacklist" \
  -d "confidenceMinimum=90" \
  -H "Key: $APIKEY" -H "Accept: application/json" \
  | python3 -c "
import sys, json
try:
    obj = json.load(sys.stdin)
    if 'data' in obj:
        for e in obj['data']:
            print(e['ipAddress'])
    else:
        print('AbuseIPDB hata:', obj.get('errors', obj), file=sys.stderr)
except Exception as ex:
    print('AbuseIPDB parse hatasi:', ex, file=sys.stderr)
" \
  | while read -r ip; do
      if is_ipv4 "$ip"; then
        ipset add $TMPSET "$ip" -exist 2>/dev/null
      fi
    done

for url in "https://www.spamhaus.org/drop/drop.txt" "https://www.spamhaus.org/drop/edrop.txt"; do
  curl -s "$url" | grep -v '^;' | awk '{print $1}' | while read -r net; do
    if [ -n "$net" ] && is_ipv4 "$net"; then
      ipset add $TMPSET "$net" -exist 2>/dev/null
    fi
  done
done

COUNT=$(ipset list $TMPSET | grep "Number of entries" | awk '{print $NF}')

if ! [[ "$COUNT" =~ ^[0-9]+$ ]] || [ "$COUNT" -lt 1000 ]; then
  echo "$(date): HATA - tmp set gecersiz/yetersiz ($COUNT), swap YAPILMADI" >&2
  ipset destroy $TMPSET 2>/dev/null
  exit 1
fi

ipset swap $TMPSET $MAINSET
ipset destroy $TMPSET

echo "$(date): blacklist guncellendi, $COUNT giris"
