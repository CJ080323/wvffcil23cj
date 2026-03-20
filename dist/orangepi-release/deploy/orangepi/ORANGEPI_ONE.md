# Orange Pi One Setup

This project can be deployed on an **Orange Pi One** as a dedicated Piso WiFi controller.

## Recommended base OS

Use an Orange Pi One image based on **Armbian** for the board. A minimal server image is the safest choice for a kiosk-style network appliance.

## Suggested hardware flow

- Orange Pi One
- microSD card
- stable 5V power supply
- Ethernet connection for WAN/LAN setup
- coin acceptor wired to the GPIO input used by [coin.py](c:/Users/CJ/Desktop/Piso%20Wifi%20Project/coin.py)

## Deployment steps

1. Flash the Orange Pi One OS image to the microSD card.
2. Boot the board and finish first boot setup.
3. Copy the app to `/opt/piso-wifi`.
4. Run:

```bash
cd /opt/piso-wifi
sudo bash deploy/orangepi/install.sh
```

5. Edit `/opt/piso-wifi/config.json`.
6. Start and verify the service:

```bash
sudo systemctl status piso-wifi.service
sudo journalctl -u piso-wifi.service -f
```

## Turn the finished card into a reusable image

After the board is fully working:

1. Shut the Orange Pi One down cleanly.
2. Remove the microSD card.
3. Use a PC imaging tool to read the full card into an `.img` file.

Common Windows tools:

- Win32 Disk Imager
- USB Image Tool

That `.img` becomes your board-specific Orange Pi One flash image.

## Notes

- Recommended captive-portal mapping: `port = 5500`, `portal_port = 80`.
- The startup script adds an `iptables` redirect from port `80` to the app port.

- The app currently expects Linux `iptables` in [firewall.py](c:/Users/CJ/Desktop/Piso%20Wifi%20Project/firewall.py).
- The GPIO coin input is `BOARD` pin `7` in [coin.py](c:/Users/CJ/Desktop/Piso%20Wifi%20Project/coin.py#L10).
- The license is device-bound, so generate the license after the Orange Pi One install has produced its final device ID.
