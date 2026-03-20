#!/usr/bin/env python3
"""
Test script to verify Omada Controller API connection
"""

import requests
import json
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration from config.json
OMADA_CONTROLLER_IP = "tplink.eap.net"
OMADA_CONTROLLER_PORT = 8043
USERNAME = "admin"
PASSWORD = "admin"


def test_connection():
    """Test basic connection to Omada Controller"""
    base_url = f"https://{OMADA_CONTROLLER_IP}:{OMADA_CONTROLLER_PORT}"
    print(f"Testing connection to {base_url}")

    # Test login
    login_url = f"{base_url}/api/v2/login"
    payload = {"username": USERNAME, "password": PASSWORD}

    try:
        print("Attempting to login...")
        response = requests.post(login_url, json=payload, verify=False, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("errorCode") == 0:
            token = data.get("result")
            print("✓ Login successful")

            # Test getting wireless networks
            session = requests.Session()
            session.headers.update(
                {"Csrf-Token": token, "Content-Type": "application/json"}
            )

            networks_url = f"{base_url}/api/v2/wireless/networks"
            print("Getting wireless networks...")
            networks_response = session.get(networks_url, verify=False, timeout=10)
            networks_response.raise_for_status()
            networks_data = networks_response.json()

            if networks_data.get("errorCode") == 0:
                networks = networks_data.get("result", [])
                print(f"✓ Found {len(networks)} wireless networks")
                for network in networks:
                    print(
                        f"  - SSID: {network.get('ssid', 'Unknown')} (ID: {network.get('id')})"
                    )

                # Get details of first network to show captive portal settings
                if networks:
                    first_network = networks[0]
                    network_id = first_network.get("id")
                    if network_id:
                        detail_url = f"{base_url}/api/v2/wireless/networks/{network_id}"
                        detail_response = session.get(
                            detail_url, verify=False, timeout=10
                        )
                        detail_response.raise_for_status()
                        detail_data = detail_response.json()

                        if detail_data.get("errorCode") == 0:
                            network_detail = detail_data.get("result", {})
                            captive_portal = network_detail.get("captivePortal", {})
                            print(
                                f"\nCaptive Portal Settings for '{first_network.get('ssid')}':"
                            )
                            print(f"  Enabled: {captive_portal.get('enable', False)}")
                            print(
                                f"  Portal IP: {captive_portal.get('portalIp', 'Not set')}"
                            )

                            return True
            else:
                print(
                    f"✗ Failed to get networks: {networks_data.get('msg', 'Unknown error')}"
                )
        else:
            print(f"✗ Login failed: {data.get('msg', 'Unknown error')}")

    except requests.exceptions.RequestException as e:
        print(f"✗ Connection error: {e}")
    except Exception as e:
        print(f"✗ Unexpected error: {e}")

    return False


if __name__ == "__main__":
    success = test_connection()
    if success:
        print("\n✓ Omada Controller API test PASSED")
    else:
        print("\n✗ Omada Controller API test FAILED")
        print("\nTroubleshooting tips:")
        print("1. Verify tplink.eap.net resolves to your Omada Controller IP")
        print("2. Check that port 8043 is accessible")
        print("3. Confirm admin/admin credentials are correct")
        print("4. Ensure Omada Controller is running and accessible")
