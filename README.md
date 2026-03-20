# Omada Controller API Control Script

This script controls TP-Link Omada Controller devices via the API, specifically configured to set the captive portal IP to 10.0.0.1.

## Configuration

Before running the script, you must update the following values in `omada_control.py`:

1. **TARGET_SSID** (Line 12): Set this to your actual Wi-Fi network name (SSID)
   ```python
   TARGET_SSID = "YOUR_SSID_HERE"  # <-- CHANGE THIS TO YOUR ACTUAL SSID
   ```

2. **OMADA_CONTROLLER_IP** (Line 8): Currently set to "tplink.eap.net"
   - If this doesn't resolve to your controller's IP, replace it with the actual IP address
   - Example: `OMADA_CONTROLLER_IP = "192.168.0.100"`

## Usage

1. Install the required Python package:
   ```bash
   pip install requests
   ```

2. Run the script:
   ```bash
   python omada_control.py
   ```

## What It Does

- Logs into your Omada Controller using admin/admin credentials
- Finds the wireless network matching your TARGET_SSID
- Configures the captive portal IP to 10.0.0.1 for that network
- Ensures the captive portal is enabled
- Preserves all other network settings

## Notes

- The script disables SSL verification since Omada Controllers often use self-signed certificates
- For production use with valid certificates, remove `verify=False` from requests
- Default Omada Controller HTTPS port is 8043 (used in this script)