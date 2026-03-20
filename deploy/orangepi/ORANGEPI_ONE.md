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
3. Update the board and verify Ethernet networking is working.
4. Copy the app to `/opt/piso-wifi`.
5. Run:

```bash
cd /opt/piso-wifi
sudo bash deploy/orangepi/install.sh
```

6. Edit `/opt/piso-wifi/config.json`.
7. Start and verify the service:

```bash
sudo systemctl restart piso-wifi.service
sudo systemctl status piso-wifi.service
sudo journalctl -u piso-wifi.service -f
```

## Recommended network modes

### Local gateway mode

Use this when the Orange Pi One is the box enforcing access time itself.

- Set `access_provider` to `local`.
- Keep `port` on `5500` and `portal_port` on `80` unless you intentionally want another mapping.
- Set `hotspot.enabled` to `true`.
- Set `hotspot.wifi_interface` to the Orange Pi Wi-Fi adapter name, commonly `wlan0`.
- Set `hotspot.wan_interface` to your internet uplink, commonly `eth0`.
- Set `hotspot.ssid` and `hotspot.passphrase` to the Wi-Fi name and password you want customers to join.
- Keep `hotspot.gateway_ip` aligned with `portal_ip`, usually `10.0.0.1`.
- Use the default DHCP range unless it conflicts with your network.
- Keep the Orange Pi on Linux with `iptables` available.
- Make sure your wider router or bridge setup sends client traffic through the Orange Pi.

### Omada integration mode

Use this when Omada APs such as the EAP110 handle the guest SSID and redirect to this app as an external portal.

- Set `access_provider` to `omada`.
- Configure the Omada controller values in `config.json` or the admin page.
- Point the Omada guest portal redirect to the Orange Pi portal URL.
- Test from a client connected to the real guest SSID so Omada appends the required portal parameters.

### Omada Controller hotspot mode

Use this when you want the Omada Controller to manage the Piso WiFi SSID and access, with the Orange Pi providing the captive portal and coin logic.

- The installer now adds `dnsmasq`.
- The service startup configures DHCP, forwarding, NAT, and the captive portal redirect automatically.
- After editing `config.json`, restart the service:

```bash
sudo systemctl restart piso-wifi.service
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

- The app supports Linux `iptables` mode and Omada controller mode in [firewall.py](c:/Users/CJ/Desktop/Piso%20Wifi%20Project/firewall.py).
- The GPIO coin input is `BOARD` pin `7` in [coin.py](c:/Users/CJ/Desktop/Piso%20Wifi%20Project/coin.py#L10).
- The license is device-bound, so generate the license after the Orange Pi One install has produced its final device ID.
