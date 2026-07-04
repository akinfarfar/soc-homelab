#!/usr/bin/env python3
import sys
import json
import requests
import os
from socket import socket, AF_UNIX, SOCK_DGRAM

OTX_KEY = "REDACTED_ROTATED_OTX_KEY"
WAZUH_SOCKET = "/var/ossec/queue/sockets/queue"

def send_alert(alert):
    msg = json.dumps(alert)
    sock = socket(AF_UNIX, SOCK_DGRAM)
    sock.connect(WAZUH_SOCKET)
    sock.send(f"1:otx:{msg}".encode())
    sock.close()

def check_otx(ip):
    try:
        url = f"https://otx.alienvault.com/api/v1/indicators/IPv4/{ip}/general"
        headers = {"X-OTX-API-KEY": OTX_KEY}
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        pulse_count = data.get("pulse_info", {}).get("count", 0)
        return pulse_count
    except:
        return 0

def main():
    alert_file = open(sys.argv[1])
    alert = json.load(alert_file)
    alert_file.close()

    ip = alert.get("data", {}).get("src_ip", "")
    if not ip:
        sys.exit(0)

    pulse_count = check_otx(ip)
    if pulse_count > 0:
        alert["otx_pulse_count"] = pulse_count
        alert["otx_malicious"] = True
        print(f"OTX: IP {ip} found in {pulse_count} pulses")

if __name__ == "__main__":
    main()
