# clickdetect_install

Sigma → Wazuh entegrasyonu (Adım 3, "Sigma" kalemi) için ClickDetect'i
wazuh-server (aarch64) üzerine **native** (Docker'sız, `uv` ile) kurar.

## Neden bu mimari (özet, ayrıntı: soc-lab-devamlilik-özeti)

- **StoW/sigma_to_wazuh elendi:** Aktif sürüm (Go, `theflakes/StoW`) yazarının
  kendi ifadesiyle "İskelet PoC" aşamasında; olgun Python sürümü ise terk
  edilmiş. İkisi de ağırlıklı Windows/Sysmon odaklı, T-Pot'un honeypot
  loglarıyla ilgisi düşük.
- **ClickDetect seçildi**, ama PPL (canlı sorgu) yolu KULLANILMADI:
  Sigma'nın OpenSearch-PPL backend'i OpenSearch 3.6'ya hizalı; wazuh-indexer
  4.14.5 ise OpenSearch 2.19.x taşıyor (majör sürüm farkı, `earliest`/`latest`
  alanları uyumsuz). Bunun yerine ClickDetect'in **Lucene Query DSL**
  (`type: opensearch`, PPL değil) datasource'u kullanılıyor - sürüme bağımlı
  değil, standart `_search` API.
- **Docker yok:** wazuh-server `aarch64`. ClickDetect saf Python olduğu için
  `uv`nin kendi yönettiği Python 3.13 ile native kurulum, Docker imajının
  arm64 desteğini araştırma riskini tamamen ortadan kaldırıyor.
- **Sigma dönüşümü ansible-time'da DEĞİL, önceden (bu repo'da) yapıldı:**
  ClickDetect'in yerleşik `sigma: true` mekanizması, OpenSearch datasource'unda
  processing pipeline'ı desteklemiyor (kaynak kodda hardcoded `None`).
  Yani T-Pot'un `data.<alan>` şemasına eşleme yapamıyor. Bunun yerine
  `files/tools/convert_sigma_rules.py` ile kurallar **elle, kendi pipeline'ımızla**
  (basit `data.` önek dönüşümü) önceden dönüştürülüp `files/rules/` altına
  statik olarak konuldu. Hedef sunucuda pysigma'ya hiç gerek yok.

## Kapsam

| Grup | Kaynak | Kural sayısı | Doğrulama |
|---|---|---|---|
| FortiGate | SigmaHQ (`rules/network/fortinet/fortigate/`) | 7 | Gerçek `data.cfgpath`/`data.action` verisiyle (25 hit) test edildi |
| Cowrie | Özel yazıldı (SigmaHQ'da hiç karşılığı yok) | 3 | `eventid` alanı gerçek veriyle doğrulandı; `cowrie_malware_staging.yml`'deki `data.input` alanı Cowrie'nin bilinen şemasından **çıkarım** - gerçek bir `cowrie.command.input` olayıyla henüz doğrulanmadı |
| Suricata | — | 0 | SigmaHQ'da `product: suricata`/`category: ids` hiç yok; Suricata zaten kendi imzasını üretiyor, Sigma katmanı değer katmıyor |

## Deploy sonrası MUTLAKA yapılması gerekenler

1. ~~`clickdetect_indexer_password` vault değişken adını doğrulayın~~ —
   **YAPILDI:** `wazuh_dashboard_admin_password` kullanılıyor, `curl` ile
   200 OK alınarak doğrulandı (indexer ve dashboard aynı admin hesabını
   paylaşıyor).
2. ~~`acl` paketi eksikliği~~ — **YAPILDI:** role artık `acl` paketini
   otomatik kuruyor (Kriz: `become_user` ile "chmod: invalid mode:
   'A+user:...:allow'" hatası, `acl` paketi eksik olduğu için oluşuyordu;
   bkz. ansible/ansible#85503). Bu sunucuda elle de kurulup deploy başarıyla
   tamamlandı (19 ok, 10 changed, 0 failed).
3. **n8n kurulduğunda:** `clickdetect_webhook_url`'i gerçek n8n webhook
   URL'iyle değiştirin ve `clickdetect_detector_active: true` yapın.
   O ana kadar servis çalışır, kuralları sorgular ama hiçbir webhook'a
   POST atmaz (`active: false`).
4. **Cowrie `data.input` alanını doğrulayın** (bkz. yukarı) - gerçek bir
   `cowrie.command.input` olayı gelince kontrol edin, gerekirse
   `files/tools/source_rules/cowrie/cowrie_malware_staging.yml`'i düzeltip
   `convert_sigma_rules.py`'yi yeniden çalıştırın.

## Yeni kural eklemek için

```bash
# hedef sunucuda ya da lokal geliştirme ortamında:
cd /opt/clickdetect/tools   # veya bu role'ün files/tools dizini
# yeni sigma kuralını source_rules/<grup>/ altına ekle
python3 convert_sigma_rules.py
# çıkan output_rules/<grup>/*.yml dosyalarını files/rules/<grup>/'a kopyala,
# ansible-playbook ile yeniden deploy et
```
