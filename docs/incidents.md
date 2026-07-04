# Ansible Fazında Karşılaşılan Bağımsız Altyapı Sorunları

## Kriz #18 — T-Pot NSG'de eksik Egress kuralı (4 Temmuz 2026)

**Bağlam:** `tpot_blacklist` Ansible rolü geliştirilirken, script izin sertleştirmesi
(`0711 → 0750`) sonrası doğrulama amacıyla `update-blacklist.sh` manuel çalıştırıldı.

**Semptom:** AbuseIPDB ve Spamhaus'a giden istekler tamamen başarısız (`HTTP_CODE:000`),
DNS çözümlemesi de dahil hiçbir dış bağlantı çalışmıyordu. Wazuh sunucusunda aynı test
sorunsuzdu — sorun VCN genelinde değil, T-Pot instance'ına özeldi.

**Teşhis:** `tcpdump` ile giden SYN paketlerinin NIC'ten çıktığı ama hiçbir yanıt
alınmadığı görüldü. OCI Console → Networking → NSG-T-Pot-Honeypot → Security Rules
incelendiğinde, bu NSG'de yalnızca bir Ingress kuralı olduğu, hiç Egress kuralı
tanımlanmadığı görüldü.

**Kök neden:** T-Pot'un ayrık Network Security Group'unda (NSG-T-Pot-Honeypot) egress
kuralı hiç oluşturulmamıştı — muhtemelen NSG ilk kurulurken sadece ingress tarafı
yapılandırılmış, egress unutulmuştu.

**Çözüm:** NSG'ye `Egress, CIDR 0.0.0.0/0, All Protocols, Allow` kuralı eklendi.
Kural eklenmesi tek başına yetmedi — T-Pot'ta `sudo reboot` sonrası bağlantı düzeldi
(NSG değişikliğinin VNIC'e tam olarak yansıması bir network stack yenilenmesi
gerektirmiş görünüyor).

**Playbook'la ilişkisi:** Bu sorun `tpot_blacklist` rolünün bir yan etkisi DEĞİLDİ —
role sadece dosya/izin/cron deploy ediyor, ağ katmanına dokunmuyor. Rastlantısal
olarak playbook doğrulaması sırasında keşfedildi.

**Ders:** Ansible rolleri "as-code" belgeleme yaparken sadece uygulama/dosya
seviyesini değil, çevresindeki bulut ağ yapılandırmasını (Security List + NSG'ler)
da envantere almak faydalı olabilir — ileride bir Terraform/OCI-CLI ile NSG
kurallarını da "as-code" hale getirmek bu tür sessiz eksiklikleri önler.
