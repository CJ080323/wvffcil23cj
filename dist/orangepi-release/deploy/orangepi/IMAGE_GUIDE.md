# Orange Pi Image Guide

You can use this project in two practical ways:

## Option 1: Ready-to-copy release package

From Windows, build a deployment zip:

```powershell
powershell -ExecutionPolicy Bypass -File deploy/orangepi/build_release.ps1
```

This creates:

```text
dist/piso-wifi-orangepi.zip
```

Use that zip after flashing a normal Orange Pi OS such as Armbian.

## Option 2: Create your own reusable SD card image

1. Flash a base Orange Pi image for your exact board model.
2. Boot the board and complete first-time setup.
3. Copy the project to `/opt/piso-wifi`.
4. Run:

```bash
cd /opt/piso-wifi
sudo bash deploy/orangepi/install.sh
```

5. Configure `config.json` and test coin, portal, firewall, and license behavior.
6. Power off the Orange Pi cleanly.
7. Clone the configured SD card into an `.img` file using a disk imaging tool.

Typical Windows tools for step 7:

- Win32 Disk Imager
- balenaEtcher clone workflows
- Raspberry Pi Imager custom image workflows

## Why this project does not ship one fixed `.img`

Orange Pi boards use different kernels, bootloaders, and device trees. A single prebuilt image is risky unless it targets one exact model, for example `Orange Pi Zero 2W` or `Orange Pi PC Plus`.

For **Orange Pi One**, use the dedicated board notes in [ORANGEPI_ONE.md](c:/Users/CJ/Desktop/Piso%20Wifi%20Project/deploy/orangepi/ORANGEPI_ONE.md) and then clone the finished microSD card into your reusable `.img`.
