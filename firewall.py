import copy
import http.cookiejar
import json
import platform
import shutil
import ssl
import subprocess
import urllib.error
import urllib.parse
import urllib.request


IPTABLES_PATH = shutil.which("iptables")
LOCAL_SUPPORTED = platform.system().lower() == "linux" and bool(IPTABLES_PATH)
DEFAULT_SETTINGS = {
    "provider": "local",
    "omada": {
        "controller_url": "",
        "controller_port": 8043,
        "controller_id": "",
        "operator_name": "",
        "operator_password": "",
        "verify_ssl": False,
        "login_version": "v5",
    },
}
_SETTINGS = copy.deepcopy(DEFAULT_SETTINGS)


def _normalize_provider(value):
    return "omada" if str(value or "").strip().lower() == "omada" else "local"


def _normalize_omada_settings(raw):
    payload = raw if isinstance(raw, dict) else {}
    login_version = str(payload.get("login_version", "v5") or "v5").strip().lower()
    if login_version not in {"v4", "v5"}:
        login_version = "v5"

    return {
        "controller_url": str(payload.get("controller_url") or "").strip().rstrip("/"),
        "controller_port": max(1, int(payload.get("controller_port", 8043) or 8043)),
        "controller_id": str(payload.get("controller_id") or "").strip().strip("/"),
        "operator_name": str(payload.get("operator_name") or "").strip(),
        "operator_password": str(payload.get("operator_password") or ""),
        "verify_ssl": bool(payload.get("verify_ssl", False)),
        "login_version": login_version,
    }


def configure(settings):
    global _SETTINGS
    merged = copy.deepcopy(DEFAULT_SETTINGS)
    if isinstance(settings, dict):
        merged["provider"] = _normalize_provider(settings.get("provider"))
        merged["omada"] = _normalize_omada_settings(settings.get("omada"))
    _SETTINGS = merged
    return access_details()


def access_details():
    provider = _normalize_provider(_SETTINGS.get("provider"))
    omada = _normalize_omada_settings(_SETTINGS.get("omada"))
    omada_ready = all(
        (
            omada["controller_url"],
            omada["operator_name"],
            omada["operator_password"],
        )
    )
    if provider == "local":
        return {
            "provider": provider,
            "ready": bool(LOCAL_SUPPORTED),
            "message": "Using local Linux firewall rules."
            if LOCAL_SUPPORTED
            else "iptables is not available on this machine.",
            "omada": {**omada, "operator_password": ""},
        }
    return {
        "provider": provider,
        "ready": omada_ready,
        "message": "Omada controller settings are ready."
        if omada_ready
        else "Complete the Omada controller settings to enable external portal authorization.",
        "omada": {**omada, "operator_password": ""},
    }


def _run_iptables(args):
    if not LOCAL_SUPPORTED:
        return False

    # Additional safety check for LSP
    if not IPTABLES_PATH:
        return False

    try:
        subprocess.run(
            [IPTABLES_PATH, *args],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except OSError:
        return False


def _local_grant(ip):
    if not ip or not isinstance(ip, str):
        return {
            "provider": "local",
            "authorized": False,
            "message": "Invalid IP address provided.",
        }
    return {
        "provider": "local",
        "authorized": bool(_run_iptables(["-I", "FORWARD", "-s", ip, "-j", "ACCEPT"])),
        "message": "Local firewall rule applied."
        if LOCAL_SUPPORTED
        else "iptables is not available on this machine.",
    }


def _local_revoke(ip):
    if not ip or not isinstance(ip, str):
        return {
            "provider": "local",
            "authorized": False,
            "message": "Invalid IP address provided.",
        }
    return {
        "provider": "local",
        "authorized": False,
        "message": "Local firewall rule removed."
        if _run_iptables(["-D", "FORWARD", "-s", ip, "-j", "ACCEPT"])
        else "iptables is not available on this machine.",
    }


def _omada_base_path(settings):
    if settings["login_version"] == "v5":
        if not settings["controller_id"]:
            raise ValueError(
                "Omada controller ID is required for controller v5 and above."
            )
        return f"/{settings['controller_id']}/api/v2/hotspot"
    return "/api/v2/hotspot"


def _build_ssl_context(verify_ssl):
    return (
        ssl.create_default_context() if verify_ssl else ssl._create_unverified_context()
    )


def _omada_request(opener, context, url, payload, headers=None):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            **(headers or {}),
        },
        method="POST",
    )
    with opener.open(request, timeout=10) as response:
        body = response.read().decode("utf-8")
    return json.loads(body or "{}")


def _omada_authorize(duration_seconds, portal_context):
    settings = _normalize_omada_settings(_SETTINGS.get("omada"))
    if not all(
        (
            settings["controller_url"],
            settings["operator_name"],
            settings["operator_password"],
        )
    ):
        return {
            "provider": "omada",
            "authorized": False,
            "message": "Omada controller settings are incomplete.",
        }

    context = portal_context if isinstance(portal_context, dict) else {}
    client_mac = str(context.get("clientMac") or "").strip()
    site = str(context.get("site") or "").strip()
    is_eap = bool(str(context.get("apMac") or "").strip())
    is_gateway = bool(str(context.get("gatewayMac") or "").strip())

    if not client_mac or not site or not (is_eap or is_gateway):
        return {
            "provider": "omada",
            "authorized": False,
            "message": "Omada portal parameters are missing. Open the portal through the Omada guest network first.",
        }

    base_url = f"{settings['controller_url']}:{settings['controller_port']}{_omada_base_path(settings)}"
    cookie_jar = http.cookiejar.CookieJar()
    ssl_context = _build_ssl_context(settings["verify_ssl"])
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar),
        urllib.request.HTTPSHandler(context=ssl_context),
    )

    try:
        login_payload = {
            "name": settings["operator_name"],
            "password": settings["operator_password"],
        }
        login_result = _omada_request(
            opener, ssl_context, f"{base_url}/login", login_payload
        )
        if int(login_result.get("errorCode", -1)) != 0:
            return {
                "provider": "omada",
                "authorized": False,
                "message": login_result.get("msg") or "Omada hotspot login failed.",
            }

        auth_payload = {
            "clientMac": client_mac,
            "site": site,
            "time": int(max(1, int(duration_seconds or 0)) * 1_000_000),
            "authType": "4",
        }
        if is_eap:
            auth_payload.update(
                {
                    "apMac": str(context.get("apMac") or "").strip(),
                    "ssidName": str(context.get("ssidName") or "").strip(),
                    "radioId": str(context.get("radioId") or "").strip(),
                }
            )
        else:
            auth_payload.update(
                {
                    "gatewayMac": str(context.get("gatewayMac") or "").strip(),
                    "vid": str(context.get("vid") or "").strip(),
                }
            )

        auth_headers = {}
        auth_url = f"{base_url}/extPortal/auth"
        token = ((login_result.get("result") or {}).get("token") or "").strip()
        if token:
            if settings["login_version"] == "v5":
                auth_headers["Csrf-Token"] = token
            else:
                auth_url = f"{auth_url}?{urllib.parse.urlencode({'token': token})}"

        auth_result = _omada_request(
            opener, ssl_context, auth_url, auth_payload, headers=auth_headers
        )
        if int(auth_result.get("errorCode", -1)) != 0:
            return {
                "provider": "omada",
                "authorized": False,
                "message": auth_result.get("msg")
                or "Omada client authorization failed.",
            }
        return {
            "provider": "omada",
            "authorized": True,
            "message": "Client authorized through Omada external portal.",
        }
    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
        return {
            "provider": "omada",
            "authorized": False,
            "message": f"Omada authorization failed: {error}",
        }


def grant_access(ip, duration_seconds=None, portal_context=None):
    provider = _normalize_provider(_SETTINGS.get("provider"))
    if provider == "omada":
        return _omada_authorize(duration_seconds, portal_context)
    return _local_grant(ip)


def revoke_access(ip):
    provider = _normalize_provider(_SETTINGS.get("provider"))
    if provider == "omada":
        return {
            "provider": "omada",
            "authorized": False,
            "message": "Omada revocation is not implemented in this build.",
        }
    return _local_revoke(ip)


def allow_user(ip):
    return bool(grant_access(ip).get("authorized"))


def block_user(ip):
    return bool(revoke_access(ip).get("authorized"))


def block_all():
    return _run_iptables(["-P", "FORWARD", "DROP"])


def _omada_request_get(opener, context, url, params=None):
    """Make a GET request to the Omada API"""
    query_string = ""
    if params:
        query_string = "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url + query_string,
        headers={"Accept": "application/json", **(params or {})},
        method="GET",
    )
    with opener.open(request, timeout=10) as response:
        body = response.read().decode("utf-8")
    return json.loads(body or "{}")


def configure_captive_portal_ip(portal_ip="10.0.0.1"):
    """Configure the captive portal IP on the Omada controller

    This function finds the wireless network and updates its captive portal settings
    to use the specified portal IP address.
    """
    settings = _normalize_omada_settings(_SETTINGS.get("omada"))
    if not all(
        (
            settings["controller_url"],
            settings["operator_name"],
            settings["operator_password"],
        )
    ):
        return {
            "provider": "omada",
            "success": False,
            "message": "Omada controller settings are incomplete.",
        }

    # Build base URL based on login version
    if settings["login_version"] == "v5":
        if not settings["controller_id"]:
            return {
                "provider": "omada",
                "success": False,
                "message": "Omada controller ID is required for controller v5 and above.",
            }
        base_path = f"/{settings['controller_id']}/api/v2"
    else:
        base_path = "/api/v2"

    base_url = f"{settings['controller_url']}:{settings['controller_port']}{base_path}"

    # Setup SSL context and opener
    ssl_context = _build_ssl_context(settings["verify_ssl"])
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar),
        urllib.request.HTTPSHandler(context=ssl_context),
    )

    try:
        # Login to Omada controller
        login_payload = {
            "name": settings["operator_name"],
            "password": settings["operator_password"],
        }
        login_url = f"{base_url}/login"
        login_result = _omada_request(opener, ssl_context, login_url, login_payload)
        if int(login_result.get("errorCode", -1)) != 0:
            return {
                "provider": "omada",
                "success": False,
                "message": login_result.get("msg") or "Omada login failed.",
            }

        # Get token for subsequent requests
        token = ((login_result.get("result") or {}).get("token") or "").strip()
        auth_headers = {}
        if token and settings["login_version"] == "v5":
            auth_headers["Csrf-Token"] = token

        # Get wireless networks to find the target SSID
        networks_url = f"{base_url}/wireless/networks"
        networks_result = _omada_request_get(opener, ssl_context, networks_url)
        if int(networks_result.get("errorCode", -1)) != 0:
            return {
                "provider": "omada",
                "success": False,
                "message": networks_result.get("msg")
                or "Failed to get wireless networks.",
            }

        networks = networks_result.get("result", [])
        if not networks:
            return {
                "provider": "omada",
                "success": False,
                "message": "No wireless networks found.",
            }

        # For now, we'll configure the first network found
        # In a more advanced implementation, we might want to match by SSID or other criteria
        target_network = networks[0]
        network_id = target_network.get("id")
        network_name = target_network.get("ssid", "Unknown")

        if not network_id:
            return {
                "provider": "omada",
                "success": False,
                "message": "Could not determine network ID.",
            }

        # Get current network details
        network_detail_url = f"{base_url}/wireless/networks/{network_id}"
        network_details = _omada_request_get(opener, ssl_context, network_detail_url)
        if int(network_details.get("errorCode", -1)) != 0:
            return {
                "provider": "omada",
                "success": False,
                "message": network_details.get("msg")
                or "Failed to get network details.",
            }

        # Update captive portal settings
        network_data = network_details.get("result", {})
        if not network_data:
            return {
                "provider": "omada",
                "success": False,
                "message": "No network data returned.",
            }

        # Ensure captivePortal section exists
        if "captivePortal" not in network_data:
            network_data["captivePortal"] = {}

        # Enable captive portal and set IP
        network_data["captivePortal"]["enable"] = True
        network_data["captivePortal"]["portalIp"] = portal_ip

        # Update the network
        update_url = f"{base_url}/wireless/networks/{network_id}"
        update_data = json.dumps(network_data).encode("utf-8")
        update_request = urllib.request.Request(
            update_url,
            data=update_data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                **auth_headers,
            },
            method="PUT",
        )

        with opener.open(update_request, timeout=10) as response:
            update_body = response.read().decode("utf-8")
        update_result = json.loads(update_body or "{}")

        if int(update_result.get("errorCode", -1)) != 0:
            return {
                "provider": "omada",
                "success": False,
                "message": update_result.get("msg")
                or "Failed to update network settings.",
            }

        return {
            "provider": "omada",
            "success": True,
            "message": f"Captive portal IP set to {portal_ip} for network '{network_name}'.",
            "network_id": network_id,
            "network_name": network_name,
            "portal_ip": portal_ip,
        }

    except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
        return {
            "provider": "omada",
            "success": False,
            "message": f"Omada captive portal configuration failed: {error}",
        }
