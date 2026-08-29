# Bu Projeyi Yeniden Kurmak

Bu belge, repo'daki Ansible rollerinin gerçek bir ortamda nasıl uygulandığını gösterir — adım adım bir "kurulum sihirbazı" değil, mimarinin nasıl bir araya geldiğinin teknik özeti.

## Ön Koşullar

- 3+ Linux sunucu (Ubuntu 22.04+ önerilir) — SIEM, honeypot fleet, tehdit istihbaratı sunucusu ayrı host'larda
- Bir NGFW/firewall cihazı (opsiyonel — FortiGate ile test edildi)
- Ansible 2.14+ kontrol makinesi
- `sops` + `age` (secrets şifreleme için) veya `ansible-vault`
- Cloudflare hesabı (Dashboard/Wazuh önü için Zero Trust Access kullanılıyorsa)

## Kurulum Sırası

Roller birbirine bağımlı olduğu için bu sırayla uygulanmalı:

1. **`hardening_ssh`** — SSH sertleştirme (parola auth kapatma, zayıf MAC'leri kaldırma). Tüm host'larda ilk adım.
2. **`hardening_ebpf`** — auditd + eBPF kural izleme kurulumu.
3. **Wazuh Manager/Indexer/Dashboard kurulumu** — tek node, cluster kapalı (bkz. `docs/diagrams/architecture.mmd`).
4. **T-Pot kurulumu** — honeypot fleet, kendi ELK stack'i devre dışı bırakılmalı (kullanılmıyorsa disk/kaynak tasarrufu için — bkz. Medium serisi).
5. **`wazuh_ufw_hardening`** — Dashboard'a erişimi Cloudflare edge IP aralıkları + admin IP ile sınırlama.
6. **`wazuh_custom_rules`** — özel tespit kuralları (`local_rules.xml`, `local_decoder.xml`) + MISP entegrasyonu.
7. **`health_monitor`** — servis sağlığı script'leri (her host'a özel `SERVICES` listesi ile).
8. **`case_manager`** — vaka yönetimi entegrasyonu (SQLite + Wazuh integration).
9. **`clickdetect_llm_triage`** — LLM tabanlı alarm triaj (opsiyonel, bir LLM sağlayıcı API anahtarı gerektirir).
10. **n8n workflow import** — `n8n/soc-triage-workflow.json`'ı n8n'in kendi arayüzünden import et, credential'ları (SMTP, MISP API key) kendi ortamına göre yeniden bağla.
11. **Dashboard panelleri** — `dashboards/wazuh-dashboard-panels.ndjson`'ı Wazuh Dashboard → Stack Management → Saved Objects → Import ile yükle.

## Önemli Notlar

- **Secrets asla düz metin commit edilmemeli.** Bu repo `sops`+`age` ve `ansible-vault`'ı birlikte kullanıyor (tutarsız ama işlevsel — gelecek bir temizlik maddesi). Kendi kurulumunda tek bir mekanizma seçmen önerilir.
- **Gerçek IP/domain'ler asla commit edilmemeli.** `.github/workflows/secrets-scan.yml` her push'ta bunu otomatik kontrol ediyor (gitleaks).
- **n8n workflow'daki credential referansları** (`credentials.smtp.id` gibi) export'ta gelmez — kendi n8n instance'ında SMTP/MISP credential'larını elle oluşturup workflow düğümlerine yeniden bağlaman gerekir.
- **Hostname çakışmasından kaçın** — birden fazla host aynı OS hostname'ini paylaşırsa (örn. varsayılan `ubuntu`), health-monitor script'lerindeki `HOST=` sabitleri karışabilir.
