#!/usr/bin/env bash
# scripts/refresh-admin-ip.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
HARDENING_VARS="inventory/group_vars/all/hardening.yml"
TPOT_NGINX_CONF="/home/ubuntu/tpotce/data/nginx/conf/tpotweb.conf"

echo "== 1/8: Yeni IP tespiti =="
NEW_IP="${1:-$(curl -4 -s ifconfig.me)}"
if [[ ! "$NEW_IP" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
  echo "HATA: gecerli bir IPv4 alinamadi: '$NEW_IP'" >&2
  exit 1
fi
echo "Yeni IP: $NEW_IP"

OLD_IP="$(grep -oP 'admin_ip:\s*"\K[0-9.]+' "$HARDENING_VARS")"
echo "Kayitli eski IP: $OLD_IP"

if [[ "$NEW_IP" == "$OLD_IP" ]]; then
  echo "IP degismemis, yapilacak bir sey yok."
  exit 0
fi

echo "== 2/8: SSH erisilebilirlik on kontrolu =="
if ! ansible tpot,wazuh -m ping --one-line >/dev/null 2>&1; then
  echo "UYARI: Ansible su an tpot/wazuh sunuculariNA SSH ile ulasamiyor." >&2
  echo "Once OCI Console Connection uzerinden elle acil erisim acin:" >&2
  echo "  TPOT: sudo ufw allow from $NEW_IP to any port 64295 proto tcp" >&2
  echo "  WAZUH: sudo ufw allow from $NEW_IP to any port 22 proto tcp" >&2
  exit 1
fi
echo "SSH erisimi dogrulandi, devam ediliyor."

echo "== 3/8: hardening.yml guncelleniyor =="
sed -i "s/admin_ip: \"$OLD_IP\"/admin_ip: \"$NEW_IP\"/" "$HARDENING_VARS"
grep "admin_ip:" "$HARDENING_VARS"

echo "== 4/8: hardening playbook calistiriliyor =="
echo "(Vault sifresini isteyecek)"
ansible-playbook playbooks/hardening.yml --diff --ask-vault-pass

echo "== 5/8: FortiGate kalo-admin adres nesnesi guncelleniyor =="
echo "(Vault sifresini tekrar isteyecek)"
ansible-playbook playbooks/fortigate-admin-ip.yml --diff --ask-vault-pass

echo "== 6/8: Eski UFW kurallari temizleniyor =="
ansible wazuh -m shell -b -a "ufw --force delete allow from $OLD_IP to any port 22 proto tcp" || true
ansible tpot  -m shell -b -a "ufw --force delete allow from $OLD_IP to any port 64295 proto tcp" || true
ansible tpot  -m shell -b -a "ufw --force delete allow from $OLD_IP to any port 64294 proto tcp" || true
ansible tpot  -m shell -b -a "ufw --force delete allow from $OLD_IP to any port 64297 proto tcp" || true

echo "== 7/8: T-Pot nginx allow-list guncelleniyor =="
ansible tpot -m shell -b -a "grep -q '$NEW_IP' $TPOT_NGINX_CONF || sed -i '/allow 127.0.0.1;/a\    allow $NEW_IP;' $TPOT_NGINX_CONF"
ansible tpot -m shell -b -a "sed -i '/allow $OLD_IP;/d' $TPOT_NGINX_CONF"

echo "-- nginx -t (syntax kontrolu) --"
ansible tpot -m shell -b -a "docker exec nginx nginx -t"

echo "-- docker restart nginx (reload YETMEZ, restart sart) --"
ansible tpot -m shell -b -a "docker restart nginx"

echo "== 8/8: Dogrulama =="
ansible tpot -m shell -b -a "docker exec nginx grep -n '$NEW_IP' /etc/nginx/conf.d/tpotweb.conf"
ansible tpot -m shell -b -a "ufw status numbered"
ansible wazuh -m shell -b -a "ufw status numbered"

echo
echo "Tamamlandi: $OLD_IP -> $NEW_IP"
echo "FortiGate kalo-admin adres nesnesi otomatik guncellendi (adim 5/8)."
