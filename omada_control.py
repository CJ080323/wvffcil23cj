import requests
import json
import sys
from requests.exceptions import RequestException
import urllib3

# Configuration - UPDATE THESE VALUES
OMADA_CONTROLLER_IP = "tplink.eap.net"  # Your Omada Controller hostname/IP
OMADA_CONTROLLER_PORT = 8043  # Default HTTPS port for Omada Controller
USERNAME = "admin"
PASSWORD = "admin"
# Set the SSID for which you want to configure the captive portal
TARGET_SSID = "YOUR_SSID_HERE"  # <-- CHANGE THIS TO YOUR ACTUAL SSID
# Set the captive portal IP you want to apply
CAPTIVE_PORTAL_IP = "10.0.0.1"


def login_to_omada(base_url):
    """Login to Omada Controller and return session with token"""
    login_url = f"{base_url}/api/v2/login"
    payload = {"username": USERNAME, "password": PASSWORD}

    try:
        response = requests.post(login_url, json=payload, verify=False)
        response.raise_for_status()
        data = response.json()

        if data.get("errorCode") == 0:
            token = data.get("result")
            session = requests.Session()
            session.headers.update(
                {"Csrf-Token": token, "Content-Type": "application/json"}
            )
            return session
        else:
            print(f"Login failed: {data.get('msg', 'Unknown error')}")
            return None
    except RequestException as e:
        print(f"Login request failed: {e}")
        return None


def get_wireless_networks(session, base_url):
    """Get list of wireless networks (SSIDs) from Omada Controller"""
    url = f"{base_url}/api/v2/wireless/networks"
    try:
        response = session.get(url, verify=False)
        response.raise_for_status()
        data = response.json()

        if data.get("errorCode") == 0:
            return data.get("result", [])
        else:
            print(
                f"Failed to get wireless networks: {data.get('msg', 'Unknown error')}"
            )
            return []
    except RequestException as e:
        print(f"Get wireless networks request failed: {e}")
        return []


def get_wireless_network_detail(session, base_url, network_id):
    """Get detailed settings for a specific wireless network"""
    url = f"{base_url}/api/v2/wireless/networks/{network_id}"
    try:
        response = session.get(url, verify=False)
        response.raise_for_status()
        data = response.json()

        if data.get("errorCode") == 0:
            return data.get("result")
        else:
            print(
                f"Failed to get wireless network details: {data.get('msg', 'Unknown error')}"
            )
            return None
    except RequestException as e:
        print(f"Get wireless network detail request failed: {e}")
        return None


def update_wireless_network(session, base_url, network_id, network_data):
    """Update a wireless network with the provided data"""
    url = f"{base_url}/api/v2/wireless/networks/{network_id}"
    try:
        response = session.put(url, json=network_data, verify=False)
        response.raise_for_status()
        data = response.json()

        if data.get("errorCode") == 0:
            print(f"Wireless network {network_id} updated successfully")
            return True
        else:
            print(
                f"Failed to update wireless network: {data.get('msg', 'Unknown error')}"
            )
            return False
    except RequestException as e:
        print(f"Update wireless network request failed: {e}")
        return False


def main():
    # Disable SSL warnings (since we use verify=False for self-signed certs)
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    base_url = f"https://{OMADA_CONTROLLER_IP}:{OMADA_CONTROLLER_PORT}"
    print(f"Connecting to Omada Controller at {base_url}")

    # Login
    session = login_to_omada(base_url)
    if not session:
        sys.exit(1)

    print("Login successful")

    # Get wireless networks
    networks = get_wireless_networks(session, base_url)
    if not networks:
        print("No wireless networks found or failed to retrieve")
        sys.exit(1)

    print(f"Found {len(networks)} wireless networks")

    # Find the target network by SSID name
    target_network = None
    for network in networks:
        if network.get("ssid") == TARGET_SSID:
            target_network = network
            break

    if not target_network:
        print(f"Wireless network with SSID '{TARGET_SSID}' not found")
        print("Available SSIDs:")
        for network in networks:
            print(f"  - {network.get('ssid', 'Unknown')} (ID: {network.get('id')})")
        sys.exit(1)

    network_id = target_network.get("id")
    print(f"Found target network '{TARGET_SSID}' (ID: {network_id})")

    # Get current network details to preserve all settings
    print("Fetching current network settings...")
    network_details = get_wireless_network_detail(session, base_url, network_id)
    if not network_details:
        print("Failed to retrieve current network settings. Aborting.")
        sys.exit(1)

    # Update captive portal IP in the settings
    # Navigate to captive portal settings - structure may vary
    if "captivePortal" not in network_details:
        network_details["captivePortal"] = {}

    # Enable captive portal if not already enabled
    network_details["captivePortal"]["enable"] = True
    network_details["captivePortal"]["portalIp"] = CAPTIVE_PORTAL_IP

    print(f"Setting captive portal IP to {CAPTIVE_PORTAL_IP} for SSID '{TARGET_SSID}'")

    # Update the network with modified settings
    if update_wireless_network(session, base_url, network_id, network_details):
        print("Captive portal IP updated successfully!")
    else:
        print("Failed to update captive portal IP")
        sys.exit(1)


if __name__ == "__main__":
    main()
