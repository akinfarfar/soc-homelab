#!/usr/bin/env python3
import sys, json, sqlite3, datetime

DB_PATH = "/opt/case-manager/cases.db"
LOG_PATH = "/var/log/case-manager/cases.json"

def main():
    alert_file = sys.argv[1]
    with open(alert_file) as f:
        alert = json.load(f)

    rule = alert.get("rule", {})
    rule_id = str(rule.get("id", "unknown"))
    description = rule.get("description", "")
    host = alert.get("data", {}).get("host") or alert.get("agent", {}).get("name") or "unknown"
    now = datetime.datetime.utcnow().isoformat() + "Z"

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, times_seen FROM cases WHERE host=? AND rule_id=? AND case_status='open'",
        (host, rule_id)
    )
    row = cur.fetchone()

    if row:
        case_id, times_seen = row
        cur.execute(
            "UPDATE cases SET last_seen=?, times_seen=? WHERE id=?",
            (now, times_seen + 1, case_id)
        )
        event = "update"
    else:
        cur.execute(
            "INSERT INTO cases (host, rule_id, description, case_status, first_seen, last_seen, times_seen) VALUES (?,?,?,?,?,?,1)",
            (host, rule_id, description, "open", now, now)
        )
        case_id = cur.lastrowid
        event = "state_change"

    conn.commit()
    conn.close()

    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({
            "timestamp": now,
            "case_id": case_id,
            "host": host,
            "rule_id": rule_id,
            "description": description,
            "case_status": "open",
            "event": event
        }) + "\n")

if __name__ == "__main__":
    main()
