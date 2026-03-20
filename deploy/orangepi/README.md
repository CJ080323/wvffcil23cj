# Orange Pi Deployment

This project is prepared for deployment on an Orange Pi running Armbian or another Debian-based Linux image.

In hotspot mode with Omada Controller, the Orange Pi acts as the portal server:

- Omada Controller manages Wi-Fi SSID and access
- `dnsmasq` gives IP addresses to clients
- Linux forwarding and NAT send clients out through the WAN port
- this Flask app provides the captive portal, timer, vouchers, and coin logic

If you are using an **Orange Pi One**, follow the board-specific notes in [ORANGEPI_ONE.md](c:/Users/CJ/Desktop/Piso%20Wifi%20Project/deploy/orangepi/ORANGEPI_ONE.md).

## 1. Flash the OS

1. Flash an Orange Pi compatible server image to the microSD card.
2. Boot the board and complete the first-login setup.
3. Confirm the board has working network access.

## 2. Copy the release to the board

Copy the project to:

```bash
/opt/piso-wifi
```

Example:

```bash
sudo mkdir -p /opt/piso-wifi
sudo rsync -av ./ /opt/piso-wifi/
```

Or copy the packaged release zip, extract it, and move the extracted files into `/opt/piso-wifi`.

## 3. Install and enable the service

Run:

```bash
cd /opt/piso-wifi
sudo bash deploy/orangepi/install.sh
```

The installer will:

- install Python, build tools, `iptables`, and `dnsmasq`
- create `/opt/piso-wifi/.venv`
- install Python dependencies
- try to install `OPi.GPIO`
- create `users_state.json` if it does not exist
- validate the Python files with `py_compile`
- install and enable the `piso-wifi.service` systemd unit

## 4. Configure the app

Edit:

```bash
sudo nano /opt/piso-wifi/config.json
```

Important values:

- `host`
- `port` and `portal_port`
- `portal_ip`
- `hotspot.ssid`
- `hotspot.passphrase`
- `hotspot.wifi_interface`
- `hotspot.wan_interface`
- `hotspot.gateway_ip`
- `hotspot.dhcp_start`
- `hotspot.dhcp_end`
- `admin_password`
- `coin_pending_seconds`
- `device_id`
- `access_provider`

This release keeps the app on port `5500`, while the public captive-portal URL stays on plain `http://10.0.0.1/`. The startup script adds an `iptables` redirect from port `80` to the app port so clients can still open the portal without typing a port number.

If you are using Omada guest portal integration:

- set `access_provider` to `omada`
- fill the `omada.controller_url`, `omada.controller_port`, `omada.controller_id`, `omada.operator_name`, and `omada.operator_password` values
- use `omada.login_version = "v5"` for newer controllers and `"v4"` for older v4.x controllers

Omada Controller manages Wi-Fi access and SSID. The Orange Pi provides the captive portal and coin logic.

You can also save these from the admin dashboard after first boot.

## 5. Start, restart, and inspect the service

```bash
sudo systemctl restart piso-wifi.service
sudo systemctl status piso-wifi.service
sudo journalctl -u piso-wifi.service -f
```

## 6. Build the Orange Pi release zip on Windows

From the project root on your Windows machine:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\orangepi\build_release.ps1
```

That produces:

```text
dist/piso-wifi-orangepi.zip
```

## Notes

- `firewall.py` supports both local Linux `iptables` mode and Omada controller mode.
- `coin.py` expects `OPi.GPIO` support on the Orange Pi.
- The license system is device-bound, so generate the license key using the device ID shown in the admin page or in `config.json`.
