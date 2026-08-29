#!/usr/bin/env python3
import subprocess
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

WAZUH_MANAGER_IP = "10.0.0.X"  # Wazuh Manager'ın VCN ici IP'si
CHECK_PORT = 1514
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "akinfarfar1@gmail.com"
SMTP_APP_PASSWORD = "YOUR_GMAIL_APP_PASSWORD"
TO_EMAIL = "cefirsin@proton.me"
STATE_FILE = "/opt/health-monitor/wazuh_heartbeat_state.txt"

def is_reachable():
    result = subprocess.run(
        ["nc", "-z", "-w", "5", WAZUH_MANAGER_IP, str(CHECK_PORT)],
        capture_output=True
    )
    return result.returncode == 0

def send_alert(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = TO_EMAIL
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_APP_PASSWORD)
        server.sendmail(SMTP_USER, [TO_EMAIL], msg.as_string())

def read_state():
    try:
        with open(STATE_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        return "unknown"

def write_state(state):
    with open(STATE_FILE, "w") as f:
        f.write(state)

def main():
    now = datetime.utcnow().isoformat()
    reachable = is_reachable()
    prev_state = read_state()

    if reachable and prev_state == "down":
        send_alert(
            "[BAGIMSIZ KONTROL] Wazuh Manager tekrar erisilebilir",
            f"Wazuh Manager ({WAZUH_MANAGER_IP}:{CHECK_PORT}) T-Pot'tan yapilan bagimsiz kontrolde tekrar erisilebilir hale geldi.\nZaman: {now}"
        )
        write_state("up")
    elif not reachable and prev_state != "down":
        send_alert(
            "[KRITIK - BAGIMSIZ KONTROL] Wazuh Manager erisilemez!",
            f"Wazuh Manager ({WAZUH_MANAGER_IP}:{CHECK_PORT}) T-Pot'tan yapilan bagimsiz kontrolde ERISILEMEZ durumda.\nBu, ana izleme sisteminin (Wazuh) kendisinin cokmus olabilecegi anlamina gelir — manuel mudahale gerekebilir.\nZaman: {now}"
        )
        write_state("down")
    elif reachable:
        write_state("up")

if __name__ == "__main__":
    main()
