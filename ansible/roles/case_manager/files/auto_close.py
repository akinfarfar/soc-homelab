#!/usr/bin/env python3
import sqlite3, datetime, json

DB_PATH = "/opt/case-manager/cases.db"
LOG_PATH = "/var/log/case-manager/cases.json"
TIMEOUT_HOURS = 24

now = datetime.datetime.utcnow()
cutoff = (now - datetime.timedelta(hours=TIMEOUT_HOURS)).isoformat() + "Z"
now_iso = now.isoformat() + "Z"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute(
    "SELECT id, host, rule_id, description FROM cases WHERE case_status='open' AND last_seen < ?",
    (cutoff,)
)
rows = cur.fetchall()

for case_id, host, rule_id, description in rows:
    cur.execute(
        "UPDATE cases SET case_status='closed_auto', closed_at=? WHERE id=?",
        (now_iso, case_id)
    )
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({
            "timestamp": now_iso,
            "case_id": case_id,
            "host": host,
            "rule_id": rule_id,
            "description": description,
            "case_status": "closed_auto",
            "event": "state_change"
        }) + "\n")

conn.commit()
conn.close()
