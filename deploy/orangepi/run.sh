#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/piso-wifi"
VENV_PATH="${APP_ROOT}/.venv"
PYTHON_BIN="${VENV_PATH}/bin/python"
HOTSPOT_SETUP_PATH="${APP_ROOT}/deploy/orangepi/setup_hotspot.sh"

cd "${APP_ROOT}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Virtual environment not found at ${PYTHON_BIN}."
  echo "Run: sudo bash ${APP_ROOT}/deploy/orangepi/install.sh"
  exit 1
fi

if [[ ! -x "${HOTSPOT_SETUP_PATH}" ]]; then
  echo "Hotspot setup script not found at ${HOTSPOT_SETUP_PATH}."
  exit 1
fi

"${HOTSPOT_SETUP_PATH}"

read -r APP_PORT PORTAL_PORT PORTAL_IP <<< "$("${PYTHON_BIN}" -c "import json; c=json.load(open('${APP_ROOT}/config.json', encoding='utf-8')); print(int(c.get('port', 5500)), int(c.get('portal_port', c.get('port', 5500))), str(c.get('portal_ip', '10.0.0.1')).strip() or '10.0.0.1')")"

if command -v iptables >/dev/null 2>&1 && [[ "${PORTAL_PORT}" != "${APP_PORT}" ]]; then
  iptables -t nat -C PREROUTING -p tcp --dport "${PORTAL_PORT}" -j REDIRECT --to-ports "${APP_PORT}" >/dev/null 2>&1 || \
    iptables -t nat -A PREROUTING -p tcp --dport "${PORTAL_PORT}" -j REDIRECT --to-ports "${APP_PORT}"

  iptables -t nat -C OUTPUT -p tcp -d "${PORTAL_IP}" --dport "${PORTAL_PORT}" -j REDIRECT --to-ports "${APP_PORT}" >/dev/null 2>&1 || \
    iptables -t nat -A OUTPUT -p tcp -d "${PORTAL_IP}" --dport "${PORTAL_PORT}" -j REDIRECT --to-ports "${APP_PORT}"
fi

exec "${PYTHON_BIN}" -u app.py
