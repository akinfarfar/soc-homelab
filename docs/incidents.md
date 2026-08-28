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

## Kriz #20 — Gözlemciyi kimse izlemiyordu: Wazuh Manager'ın kendisi tek hata noktasıydı (28 Ağustos 2026)
**Bağlam:** Aşama 1 genel sağlık denetimi sırasında, tüm izleme/alarm zincirinin (health-monitor,
case-manager, ClickDetect, n8n) tek dayanağının Wazuh Manager'ın kendisi olduğu fark edildi.
**Semptom:** `wazuh-manager.service`'in systemd yapılandırmasında `Restart=no` olduğu görüldü —
süreç herhangi bir sebeple çökerse (OOM, beklenmeyen exception) systemd onu OTOMATİK OLARAK
yeniden başlatmıyordu, biri fark edip elle müdahale edene kadar ölü kalabilirdi. Dış/bağımsız
hiçbir izleme mekanizması da yoktu (OCI Monitoring hiç kurulmamıştı).
**Teşhis:** `systemctl show wazuh-manager` ile `Restart=no` doğrulandı.
**Kök neden:** Tüm sağlık izleme zinciri, izlediği sistemin (Wazuh) kendisine bağımlı kurulmuştu —
döngüsel bir bağımlılık, klasik bir tek hata noktası (SPOF).
**Çözüm:** İki katmanlı düzeltme: (1) `/etc/systemd/system/wazuh-manager.service.d/override.conf`
ile `Restart=on-failure` eklendi; (2) T-Pot'tan (Wazuh Manager'dan tamamen bağımsız bir host)
periyodik, doğrudan Gmail SMTP üzerinden e-posta gönderen bir nabız kontrolü script'i kuruldu
(cron her 5 dakikada bir). Kurulum sırasında üç ayrı hata bulunup düzeltildi: yanlış port seçimi
(55000 yerine 1514), eksik `if __name__ == "__main__":` koruması (import sırasında script'in
kendiliğinden çalışıp istenmeyen bir alarm göndermesine sebep oldu), ve public/iç IP karışıklığı
(ufw kuralı sadece VCN içi IP'ye izin veriyordu). Gerçek bir down/up döngüsü simüle edilip
e-postanın doğru çalıştığı doğrulandı.
**Ders:** Bir izleme sisteminin kendisi de izlenmelidir — "kim gözlemciyi izliyor" sorusu,
mimari tamamlandıktan çok sonra bile sorulmaya değer. Ayrıca: yeni bir script'i test ederken
seçtiğiniz test parametrelerinin (port, IP) gerçek ağ topolojisiyle uyumlu olduğunu baştan
doğrulamak, yanlış pozitiflerden kaçınmanın en ucuz yolu.

## Kriz #21 — Ansible reposunda git geçmişinde sızmış production IP'leri (28 Ağustos 2026)
**Bağlam:** Ansible reposunun untracked (hiç commit edilmemiş) dosyalarının, repo public
olacağı için secrets/gerçek IP açısından taranması sırasında ortaya çıktı.
**Semptom:** `inventory.ini`'de dört production host'un (Wazuh, T-Pot, MISP, FortiGate)
gerçek public IP'leri düz metin bulundu, hiçbir gitignore kuralı kapsamıyordu.
`wazuh_ufw_hardening/defaults/main.yml`'de kullanıcının gerçek admin IP'si hardcoded duruyordu.
**Teşhis:** Daha derin bir tarama (`git diff` + `git log --all -p`) yapılınca, ZATEN TRACKED
olan `hardening.yml` dosyasının önceki commit edilmiş halinin de düz metin bir (eski) admin IP
içerdiği görüldü — sorun sadece untracked dosyalarla sınırlı değildi, git GEÇMİŞİNDE de
gerçek IP'ler vardı. `git log --all -p` ile tam tarama yapılıp toplam 5 gerçek IP bulundu.
**Kök neden:** Secrets/IP hijyeni disiplini (`.sops.yaml`, ansible-vault kullanımı) bir noktaya
kadar vardı, ama tutarlı şekilde her dosyaya/her commit'e uygulanmamıştı.
**Çözüm:** `git-filter-repo` kurulup (`pip3 install git-filter-repo --break-system-packages`)
`--replace-text` ile tüm geçmiş RFC5737 (belgeleme amaçlı ayrılmış) placeholder IP'lerle
temizlendi. İlginç bir keşif: script "The previous run is older than a day" uyarısı verdi —
bu temizlik DAHA ÖNCE de bir kez yapılmış, ama sonradan yeni bir commit'te tekrar düz metin
IP eklenmiş, yani koruma kalıcı olmamıştı. Kalan dosyalar (`inventory.ini`, `hardening.yml`)
ansible-vault ile şifrelendi, hardcoded admin_ip placeholder'a çevrildi. Son tarama temiz
çıkınca 27 dosya tek commit'te birleştirildi, `gh` CLI ile GitHub'da bir PRIVATE repo
oluşturulup temizlenmiş geçmiş push edildi.
**Ders:** Bir güvenlik temizliğinin "daha önce yapılmış olması", kalıcı olduğu anlamına
gelmez — eğer temizlik disiplini (pre-commit hook, CI kontrolü gibi) süreçselleştirilmezse,
bir sonraki commit aynı hatayı sessizce geri getirebilir. Tek seferlik bir düzeltme,
tekrarlayan bir kontrolle desteklenmedikçe kalıcı değildir.
