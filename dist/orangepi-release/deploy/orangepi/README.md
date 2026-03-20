# Orange Pi Deployment

This project is prepared for deployment on an Orange Pi running a Linux-based OS such as Armbian.

If you are using an **Orange Pi One**, follow the board-specific notes in [ORANGEPI_ONE.md](c:/Users/CJ/Desktop/Piso%20Wifi%20Project/deploy/orangepi/ORANGEPI_ONE.md).

## 1. Flash the OS

1. Flash an Orange Pi compatible image to an SD card or eMMC.
2. Boot the board and complete normal OS setup.
3. Make sure Python 3 and networking are available.

## 2. Copy the project

Copy this project to:

```bash
/opt/piso-wifi
```

Example:

```bash
sudo mkdir -p /opt/piso-wifi
sudo rsync -av ./ /opt/piso-wifi/
```

## 3. Install and enable the service

Run:

```bash
cd /opt/piso-wifi
sudo bash deploy/orangepi/install.sh
```

This will:

- install Python dependencies
- create a virtual environment
- install the `piso-wifi.service` systemd unit
- enable automatic startup on boot

## 4. Configure the app

Edit:

```bash
/opt/piso-wifi/config.json
```

Important values:

- `host`
- `port`
- `portal_ip`
- `portal_port`
- `admin_password`
- `coin_pending_seconds`
- `device_id`

Recommended values for captive-portal use:

- keep `port` on `5500`
- keep `portal_port` on `80`
- let the startup script install the `iptables` redirect from port `80` to the app port

## 5. Check service status

```bash
sudo systemctl status piso-wifi.service
sudo journalctl -u piso-wifi.service -f
```

## Notes

- `firewall.py` expects Linux `iptables`.
- `coin.py` expects `OPi.GPIO` support on the Orange Pi.
- The license system is device-bound, so generate the license key using the device ID shown in the admin page or `config.json`.
