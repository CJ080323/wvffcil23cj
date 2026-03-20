#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/piso-wifi"
VENV_PATH="${APP_ROOT}/.venv"
PYTHON_BIN="${VENV_PATH}/bin/python"
DNSMASQ_TEMPLATE="${APP_ROOT}/deploy/orangepi/templates/dnsmasq.conf.template"
DNSMASQ_CONF="/etc/dnsmasq.d/piso-wifi.conf"

if [[ "${EUID}" -ne 0 ]]; then
  echo "setup_hotspot.sh must run as root."
  exit 1
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Python virtual environment not found at ${PYTHON_BIN}."
  exit 1
fi

if [[ ! -f "${APP_ROOT}/config.json" ]]; then
  echo "Config file not found at ${APP_ROOT}/config.json."
  exit 1
fi

mapfile -t HOTSPOT_VALUES < <("${PYTHON_BIN}" -c "
import json
from pathlib import Path

config = json.loads(Path('${APP_ROOT}/config.json').read_text(encoding='utf-8'))
hotspot = config.get('hotspot') or {}

enabled = '1' if hotspot.get('enabled', True) else '0'
ssid = str(hotspot.get('ssid') or 'PisoWiFi').strip() or 'PisoWiFi'
passphrase = str(hotspot.get('passphrase') or 'pisowifi123').strip()
if len(passphrase) < 8:
    passphrase = 'pisowifi123'
channel = str(int(hotspot.get('channel', 6) or 6))
wifi_interface = str(hotspot.get('wifi_interface') or 'wlan0').strip() or 'wlan0'
wan_interface = str(hotspot.get('wan_interface') or 'eth0').strip() or 'eth0'
gateway_ip = str(hotspot.get('gateway_ip') or config.get('portal_ip') or '10.0.0.1').strip() or '10.0.0.1'
dhcp_start = str(hotspot.get('dhcp_start') or '10.0.0.50').strip() or '10.0.0.50'
dhcp_end = str(hotspot.get('dhcp_end') or '10.0.0.150').strip() or '10.0.0.150'
lease_hours = str(int(hotspot.get('lease_hours', 12) or 12))
country_code = (str(hotspot.get('country_code') or 'PH').strip() or 'PH')[:2].upper()
hidden = '1' if hotspot.get('hidden', False) else '0'

for value in (
    enabled,
    ssid,
    passphrase,
    channel,
    wifi_interface,
    wan_interface,
    gateway_ip,
    dhcp_start,
    dhcp_end,
    lease_hours,
    country_code,
    hidden,
):
    print(value)
")

HOTSPOT_ENABLED="${HOTSPOT_VALUES[0]}"
SSID="${HOTSPOT_VALUES[1]}"
PASSPHRASE="${HOTSPOT_VALUES[2]}"
CHANNEL="${HOTSPOT_VALUES[3]}"
WIFI_INTERFACE="${HOTSPOT_VALUES[4]}"
WAN_INTERFACE="${HOTSPOT_VALUES[5]}"
GATEWAY_IP="${HOTSPOT_VALUES[6]}"
DHCP_START="${HOTSPOT_VALUES[7]}"
DHCP_END="${HOTSPOT_VALUES[8]}"
LEASE_HOURS="${HOTSPOT_VALUES[9]}"
COUNTRY_CODE="${HOTSPOT_VALUES[10]}"
HIDDEN="${HOTSPOT_VALUES[11]}"

if [[ "${HOTSPOT_ENABLED}" != "1" ]]; then
  echo "Hotspot mode is disabled in config.json."
  exit 0
fi

HOST_CIDR="${GATEWAY_IP}/24"
DHCP_RANGE="${DHCP_START},${DHCP_END},255.255.255.0,${LEASE_HOURS}h"
IGNORE_BROADCAST_SSID="0"
if [[ "${HIDDEN}" == "1" ]]; then
  IGNORE_BROADCAST_SSID="1"
fi

export SSID PASSPHRASE CHANNEL WIFI_INTERFACE WAN_INTERFACE GATEWAY_IP DHCP_RANGE COUNTRY_CODE IGNORE_BROADCAST_SSID

mkdir -p /etc/dnsmasq.d

## hostapd setup removed for Omada integration

sed \
  -e "s|{{WIFI_INTERFACE}}|${WIFI_INTERFACE}|g" \
  -e "s|{{GATEWAY_IP}}|${GATEWAY_IP}|g" \
  -e "s|{{DHCP_RANGE}}|${DHCP_RANGE}|g" \
  "${DNSMASQ_TEMPLATE}" > "${DNSMASQ_CONF}"

## hostapd config removed for Omada integration

## WiFi interface setup handled by Omada Controller

printf 'net.ipv4.ip_forward=1\n' > /etc/sysctl.d/98-piso-wifi.conf
sysctl -p /etc/sysctl.d/98-piso-wifi.conf >/dev/null

iptables -t nat -C POSTROUTING -o "${WAN_INTERFACE}" -j MASQUERADE >/dev/null 2>&1 || \
  iptables -t nat -A POSTROUTING -o "${WAN_INTERFACE}" -j MASQUERADE

iptables -C FORWARD -i "${WAN_INTERFACE}" -o "${WIFI_INTERFACE}" -m state --state RELATED,ESTABLISHED -j ACCEPT >/dev/null 2>&1 || \
  iptables -A FORWARD -i "${WAN_INTERFACE}" -o "${WIFI_INTERFACE}" -m state --state RELATED,ESTABLISHED -j ACCEPT

iptables -C FORWARD -i "${WIFI_INTERFACE}" -o "${WAN_INTERFACE}" -j ACCEPT >/dev/null 2>&1 || \
  iptables -A FORWARD -i "${WIFI_INTERFACE}" -o "${WAN_INTERFACE}" -j ACCEPT

systemctl enable dnsmasq >/dev/null
systemctl restart dnsmasq
echo "Hotspot ready (Omada managed)."
echo "Gateway: ${GATEWAY_IP}"
echo "WAN uplink: ${WAN_INTERFACE}"
