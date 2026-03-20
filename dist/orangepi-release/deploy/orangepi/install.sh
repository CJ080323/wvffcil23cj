#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/opt/piso-wifi"
SERVICE_NAME="piso-wifi.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
RUNNER_PATH="${APP_ROOT}/deploy/orangepi/run.sh"
VENV_PATH="${APP_ROOT}/.venv"

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
apt-get install -y python3 python3-venv python3-pip python3-dev build-essential iptables

python3 -m venv "${VENV_PATH}"
"${VENV_PATH}/bin/pip" install --upgrade pip
"${VENV_PATH}/bin/pip" install -r "${APP_ROOT}/requirements.txt"

if ! "${VENV_PATH}/bin/python" -c "import OPi.GPIO" >/dev/null 2>&1; then
  "${VENV_PATH}/bin/pip" install OPi.GPIO || true
fi

chmod +x "${RUNNER_PATH}"
install -m 0644 "${APP_ROOT}/deploy/orangepi/piso-wifi.service" "${SERVICE_PATH}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo
echo "Piso WiFi installed."
echo "Check service status with: systemctl status ${SERVICE_NAME}"
