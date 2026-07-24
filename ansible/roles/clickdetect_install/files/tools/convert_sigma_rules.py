#!/usr/bin/env python3
"""
Sigma -> ClickDetect dönüştürme aracı.

ClickDetect'in yerleşik `sigma: true` mekanizması, OpenSearch datasource'unda
processing pipeline'ı desteklemiyor (bkz. clickdetect/detector/datasource/opensearch.py
-> OpensearchLuceneBackend(None, ...)). Bu yüzden dönüşümü burada, kendi
pipeline'ımızla (T-Pot alan adı eşlemesi) elle yapıp sonucu ClickDetect'in
native (sigma:false) kural formatına gömüyoruz.

Kullanım:
    python3 convert_sigma_rules.py

Girdi:  source_rules/<grup>/*.yml  (ham Sigma kuralları)
Çıktı:  output_rules/<grup>/<kural_id>.yml  (ClickDetect native kuralları)
"""
import glob
import json
import os
import sys
import yaml

from sigma.processing.transformations import AddFieldnamePrefixTransformation
from sigma.processing.pipeline import ProcessingPipeline, ProcessingItem
from sigma.backends.opensearch.opensearch import OpensearchLuceneBackend
from sigma.collection import SigmaCollection

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(SCRIPT_DIR, "source_rules")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output_rules")
INDEX_PATTERN = "wazuh-alerts-4.x-*"

# T-Pot / Wazuh indeksinde her ürün grubu "data." önekiyle saklanıyor
# (Suricata, Cowrie, FortiGate hepsi doğrulandı - bkz. devamlılık notları).
# Alt alan adı farklılıkları (dest_ip/dst_ip vb.) şu an dönüştürdüğümüz
# kural setlerinde sorun çıkarmıyor; ileride yeni kurallar eklenirse
# gerekirse FieldMappingTransformation ile per-product override eklenir.
PIPELINE = ProcessingPipeline(
    name="tpot_data_prefix",
    priority=20,
    items=[
        ProcessingItem(
            identifier="data_prefix",
            transformation=AddFieldnamePrefixTransformation(prefix="data."),
        ),
    ],
)

# ClickDetect Rule şeması `id` alanının STRING olmasını istiyor (bkz. docs/rules.md)
# ve dosya başına tek kural varsayıyoruz (SigmaCollection her dosyada tek kural içeriyor).


def build_query_body(lucene_query: str) -> dict:
    """Dönüştürülmüş Lucene query_string'i, zaman aralığı filtresiyle
    birlikte tam bir OpenSearch _search gövdesine sarar."""
    return {
        "query": {
            "bool": {
                "must": [
                    {"query_string": {"query": lucene_query, "analyze_wildcard": True}}
                ],
                "filter": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": "{{ startime }}",
                                "lte": "{{ endtime }}",
                                "format": "epoch_second",
                            }
                        }
                    }
                ],
            }
        }
    }


def sigma_level_to_int(level: str) -> int:
    return {"informational": 3, "low": 5, "medium": 8, "high": 12, "critical": 15}.get(
        level, 8
    )


def convert_one(sigma_path: str, group: str) -> dict:
    raw = open(sigma_path).read()
    sigma_yaml = yaml.safe_load(raw)

    backend = OpensearchLuceneBackend(PIPELINE, index_names=[INDEX_PATTERN])
    rule_data = SigmaCollection.from_yaml(raw)
    result = backend.convert(rule_data, output_format="dsl_lucene")
    if not result:
        raise ValueError(f"{sigma_path}: sonuç üretmedi")
    lucene_query = result[0]["query"]["bool"]["must"][0]["query_string"]["query"]

    body = build_query_body(lucene_query)

    clickdetect_rule = {
        "id": sigma_yaml["id"],
        "name": sigma_yaml["title"],
        "level": sigma_level_to_int(sigma_yaml.get("level", "medium")),
        "size": ">0",
        "active": True,
        "author": [sigma_yaml.get("author", "unknown")],
        "group": group,
        "tags": sigma_yaml.get("tags", []),
        "description": (sigma_yaml.get("description", "") or "").strip(),
        "sigma": False,  # ÖNEMLİ: pipeline'sız yerleşik sigma yoluna DÜŞMESİN
        "data": {"source_sigma_id": sigma_yaml["id"]},
        "rule": json.dumps(body, indent=2, ensure_ascii=False),
    }
    return clickdetect_rule


def main():
    total, failed = 0, 0
    for group_dir in sorted(glob.glob(os.path.join(SOURCE_DIR, "*"))):
        group = os.path.basename(group_dir)
        out_dir = os.path.join(OUTPUT_DIR, group)
        os.makedirs(out_dir, exist_ok=True)
        for sigma_file in sorted(glob.glob(os.path.join(group_dir, "*.yml"))):
            total += 1
            try:
                rule = convert_one(sigma_file, group)
            except Exception as ex:
                failed += 1
                print(f"FAIL {sigma_file}: {ex}", file=sys.stderr)
                continue
            out_name = os.path.basename(sigma_file)
            out_path = os.path.join(out_dir, out_name)
            rule_json_text = rule.pop("rule")
            with open(out_path, "w") as f:
                f.write("# OTOMATIK ÜRETİLDİ - elle düzenlemeyin.\n")
                f.write(f"# Kaynak: {sigma_file}\n")
                f.write("# Üretici: convert_sigma_rules.py\n")
                yaml.dump(rule, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
                f.write("rule: |-\n")
                for line in rule_json_text.splitlines():
                    f.write(f"  {line}\n")
            print(f"OK   {sigma_file} -> {out_path}")
    print(f"\nToplam: {total}, Başarısız: {failed}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
