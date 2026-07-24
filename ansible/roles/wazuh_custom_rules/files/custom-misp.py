#!/usr/bin/env python3
import sys
import json
import ipaddress
import requests
from socket import socket, AF_UNIX, SOCK_DGRAM

WAZUH_SOCKET = "/var/ossec/queue/sockets/queue"

SRC_IP_FIELDS = ("src_ip", "srcip", "source_ip")
DST_IP_FIELDS = ("dest_ip", "dst_ip", "dstip", "destination_ip")


def find_ip(data, field_names):
    for name in field_names:
        val = data.get(name)
        if val:
            return val
    return None


def is_internal(ip_str):
    try:
        return ipaddress.ip_address(ip_str).is_private
    except ValueError:
        return False


def get_external_ip(data):
    src = find_ip(data, SRC_IP_FIELDS)
    dst = find_ip(data, DST_IP_FIELDS)
    candidates = [ip for ip in (src, dst) if ip and not is_internal(ip)]
    unique = list(dict.fromkeys(candidates))
    if len(unique) == 1:
        return unique[0]
    return None


def query_misp(ip, misp_url, api_key):
    headers = {
        "Authorization": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    body = {"value": ip, "returnFormat": "json"}
    response = requests.post(
        f"{misp_url}/attributes/restSearch",
        headers=headers,
        json=body,
        verify=True,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def send_to_wazuh(payload):
    """custom-alienvault.py'daki ayni desen: sonucu Wazuh'un kendi kuyruk
    soketine yazip yeni bir log olarak yeniden analysisd'e soktur - print()
    stdout'a yazmak sadece integratord'un kendi debug logunda kaliyor,
    kural motoruna hic ulasmiyor."""
    msg = json.dumps(payload)
    sock = socket(AF_UNIX, SOCK_DGRAM)
    sock.connect(WAZUH_SOCKET)
    sock.send(f"1:misp:{msg}".encode())
    sock.close()


def main():
    if len(sys.argv) < 4:
        sys.exit(1)

    alert_file_path = sys.argv[1]
    api_key = sys.argv[2]
    misp_url = sys.argv[3]

    with open(alert_file_path) as f:
        alert = json.load(f)

    data = alert.get("data", {})
    ip = get_external_ip(data)

    if not ip:
        sys.exit(0)

    try:
        result = query_misp(ip, misp_url, api_key)
    except Exception as exc:
        payload = {"integration": "misp", "misp": {"status": "error", "checked_ip": ip, "error": str(exc)}}
        send_to_wazuh(payload)
        print(json.dumps(payload))
        sys.exit(0)

    attributes = result.get("response", {}).get("Attribute", [])
    if attributes:
        attr = attributes[0]
        payload = {
            "integration": "misp",
            "misp": {
                "status": "match",
                "checked_ip": ip,
                "value": attr.get("value"),
                "category": attr.get("category"),
                "type": attr.get("type"),
                "event_id": attr.get("event_id"),
                "comment": attr.get("comment", ""),
            },
        }
    else:
        payload = {"integration": "misp", "misp": {"status": "no_match", "checked_ip": ip}}

    send_to_wazuh(payload)
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
