#!/usr/bin/env python3
import sqlite3, datetime, json, sys

if len(sys.argv) != 2:
    print("Kullanim: close_case.py <case_id>")
    sys.exit(1)

case_id = int(sys.argv[1])
DB_PATH = "/opt/case-manager/cases.db"
LOG_PATH = "/var/log/case-manager/cases.json"
now_iso = datetime.datetime.utcnow().isoformat() + "Z"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT host, rule_id, description, case_status FROM cases WHERE id=?", (case_id,))
row = cur.fetchone()

if not row:
    print(f"Vaka #{case_id} bulunamadi.")
    sys.exit(1)

host, rule_id, description, status = row
if status != "open":
    print(f"Vaka #{case_id} zaten '{status}' durumunda, islem yapilmadi.")
    sys.exit(0)

cur.execute("UPDATE cases SET case_status='closed_manual', closed_at=? WHERE id=?", (now_iso, case_id))
conn.commit()
conn.close()

with open(LOG_PATH, "a") as f:
    f.write(json.dumps({
        "timestamp": now_iso,
        "case_id": case_id,
        "host": host,
        "rule_id": rule_id,
        "description": description,
        "case_status": "closed_manual",
        "event": "state_change"
    }) + "\n")

print(f"Vaka #{case_id} kapatildi.")
