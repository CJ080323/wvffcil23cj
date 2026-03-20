#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/piso-wifi"
SERVICE_NAME="piso-wifi.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
RUNNER_PATH="${APP_ROOT}/deploy/orangepi/run.sh"
HOTSPOT_SETUP_PATH="${APP_ROOT}/deploy/orangepi/setup_hotspot.sh"
VENV_PATH="${APP_ROOT}/.venv"
PYTHON_BIN="${VENV_PATH}/bin/python"
PIP_BIN="${VENV_PATH}/bin/pip"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this installer as root: sudo bash deploy/orangepi/install.sh"
  exit 1
fi

if [[ ! -f "${APP_ROOT}/app.py" ]]; then
  echo "Expected app.py under ${APP_ROOT}."
  echo "Copy this project folder to ${APP_ROOT} first."
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip python3-dev build-essential iptables iproute2 dnsmasq rfkill

python3 -m venv "${VENV_PATH}"
"${PIP_BIN}" install --upgrade pip
"${PIP_BIN}" install -r "${APP_ROOT}/requirements.txt"

if ! "${PYTHON_BIN}" -c "import OPi.GPIO" >/dev/null 2>&1; then
  "${PIP_BIN}" install OPi.GPIO || true
fi

if [[ ! -f "${APP_ROOT}/users_state.json" ]]; then
  printf '{\n  "saved_at": 0,\n  "users": {},\n  "vouchers": {}\n}\n' > "${APP_ROOT}/users_state.json"
fi

chmod +x "${RUNNER_PATH}"
chmod +x "${HOTSPOT_SETUP_PATH}"
chmod 600 "${APP_ROOT}/config.json" || true

"${PYTHON_BIN}" -m py_compile \
  "${APP_ROOT}/app.py" \
  "${APP_ROOT}/firewall.py" \
  "${APP_ROOT}/coin.py" \
  "${APP_ROOT}/generate_license.py"

install -m 0644 "${APP_ROOT}/deploy/orangepi/piso-wifi.service" "${SERVICE_PATH}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo
echo "Piso WiFi installed."
echo "Check service status with: systemctl status ${SERVICE_NAME}"
echo "Follow logs with: journalctl -u ${SERVICE_NAME} -f"
