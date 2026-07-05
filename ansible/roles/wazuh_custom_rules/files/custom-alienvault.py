#!/usr/bin/env python3
import sys
import os
import json
import requests
import subprocess
from socket import socket, AF_UNIX, SOCK_DGRAM

WAZUH_SOCKET = "/var/ossec/queue/sockets/queue"
SOPS_SECRETS_FILE = "/var/ossec/etc/otx.yaml"
SOPS_AGE_KEY_FILE = "/etc/sops/age/keys.txt"


def get_otx_key():
    env = os.environ.copy()
    env["SOPS_AGE_KEY_FILE"] = SOPS_AGE_KEY_FILE
    try:
        result = subprocess.run(
            ["sops", "--decrypt", "--extract", '["otx_api_key"]', SOPS_SECRETS_FILE],
            capture_output=True, text=True, env=env, timeout=10
        )
        if result.returncode != 0:
            sys.stderr.write(f"OTX: sops decrypt failed: {result.stderr}\n")
            return None
        return result.stdout.strip()
    except Exception as e:
        sys.stderr.write(f"OTX: could not decrypt key: {e}\n")
        return None


def send_alert(alert):
    msg = json.dumps(alert)
    sock = socket(AF_UNIX, SOCK_DGRAM)
    sock.connect(WAZUH_SOCKET)
    sock.send(f"1:otx:{msg}".encode())
    sock.close()


def check_otx(ip, api_key):
    try:
        url = f"https://otx.alienvault.com/api/v1/indicators/IPv4/{ip}/general"
        headers = {"X-OTX-API-KEY": api_key}
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        pulse_count = data.get("pulse_info", {}).get("count", 0)
        return pulse_count
    except Exception:
        return 0


def main():
    alert_file = open(sys.argv[1])
    alert = json.load(alert_file)
    alert_file.close()

    ip = alert.get("data", {}).get("src_ip", "")
    if not ip:
        sys.exit(0)

    api_key = get_otx_key()
    if not api_key:
        sys.exit(0)

    pulse_count = check_otx(ip, api_key)
    if pulse_count > 0:
        alert["otx_pulse_count"] = pulse_count
        alert["otx_malicious"] = True
        print(f"OTX: IP {ip} found in {pulse_count} pulses")


if __name__ == "__main__":
    main()
