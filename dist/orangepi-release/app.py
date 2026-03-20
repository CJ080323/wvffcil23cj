from flask import Flask, jsonify, redirect, render_template, request, session
import base64
import hashlib
import hmac
import json
import os
import secrets
import string
import threading
import time
import uuid
from datetime import datetime, timezone

from coin import gpio_available, wait_coin
from firewall import allow_user, block_user


BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATE_PATH = os.path.join(BASE_DIR, "users_state.json")
RATE_AMOUNTS = (1, 5, 10, 20)
DEFAULT_SECONDS_PER_PESO = 600
DEFAULT_ACCENT_COLOR = "#d8871f"
DEFAULT_SITE_NAME = "Piso WiFi"
LICENSE_PREFIX = "PWF1"
LICENSE_SIGNATURE_LENGTH = 12
LICENSE_SIGNING_SECRET = "piso-wifi-license-v1"
DEVICE_ID_LENGTH = 12
DEFAULT_CONFIG = {
    "seconds_per_peso": DEFAULT_SECONDS_PER_PESO,
    "rate_seconds": {
        "1": DEFAULT_SECONDS_PER_PESO,
        "5": DEFAULT_SECONDS_PER_PESO * 5,
        "10": DEFAULT_SECONDS_PER_PESO * 10,
        "20": DEFAULT_SECONDS_PER_PESO * 20,
    },
    "admin_password": "admin123",
    "host": "10.0.0.1",
    "port": 80,
    "portal_ip": "10.0.0.1",
    "portal_port": 80,
    "secret_key": "change-me",
    "coin_pending_seconds": 60,
    "voucher_code_length": 8,
    "accent_color": DEFAULT_ACCENT_COLOR,
    "site_name": DEFAULT_SITE_NAME,
    "logo_url": "",
    "license_key": "",
    "device_id": "",
}


def normalize_rate_seconds(raw_rates, base_seconds):
    normalized = {}
    base = max(1, int(base_seconds or DEFAULT_SECONDS_PER_PESO))

    for amount in RATE_AMOUNTS:
        fallback = amount * base
        value = fallback
        if isinstance(raw_rates, dict):
            try:
                value = int(raw_rates.get(str(amount), fallback))
            except (TypeError, ValueError):
                value = fallback
        normalized[str(amount)] = max(60, value)

    return normalized


def normalize_hex_color(value, fallback=DEFAULT_ACCENT_COLOR):
    candidate = str(value or "").strip()
    if len(candidate) == 7 and candidate.startswith("#"):
        hex_part = candidate[1:]
        if all(char in string.hexdigits for char in hex_part):
            return f"#{hex_part.lower()}"
    return fallback


def normalize_text(value, fallback=""):
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned or fallback


def normalize_device_id(value):
    cleaned = "".join(char for char in str(value or "").upper() if char.isalnum())
    return cleaned[:DEVICE_ID_LENGTH]


def generate_device_id():
    return uuid.uuid4().hex[:DEVICE_ID_LENGTH].upper()


def normalize_logo_url(value):
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    lowered = candidate.lower()
    if lowered.startswith(("http://", "https://", "/", "static/")):
        return candidate
    return ""


def decode_license_name(token):
    try:
        padding = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(f"{token}{padding}".encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return ""
    return normalize_text(decoded)


def encode_license_name(name):
    cleaned = normalize_text(name)
    encoded = base64.urlsafe_b64encode(cleaned.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def parse_license_key(license_key):
    key = str(license_key or "").strip()
    device_id = normalize_device_id(config.get("device_id"))
    if not key:
        return {
            "valid": False,
            "status": "missing",
            "message": "No license key installed.",
            "license_key": "",
            "licensed_to": "",
            "expires_on": None,
            "device_id": device_id,
        }

    parts = key.split("-")
    if len(parts) != 5 or parts[0] != LICENSE_PREFIX:
        return {
            "valid": False,
            "status": "invalid",
            "message": "License key format is invalid for this device.",
            "license_key": key,
            "licensed_to": "",
            "expires_on": None,
            "device_id": device_id,
        }

    _, expiry_token, name_token, device_token, signature = parts
    normalized_device_token = normalize_device_id(device_token)
    if not device_id or normalized_device_token != device_id:
        return {
            "valid": False,
            "status": "invalid",
            "message": "License key does not match this device ID.",
            "license_key": key,
            "licensed_to": "",
            "expires_on": None,
            "device_id": device_id,
        }

    expected_signature = hmac.new(
        LICENSE_SIGNING_SECRET.encode("utf-8"),
        f"{expiry_token}:{name_token}:{normalized_device_token}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:LICENSE_SIGNATURE_LENGTH]

    if signature.lower() != expected_signature:
        return {
            "valid": False,
            "status": "invalid",
            "message": "License signature is invalid.",
            "license_key": key,
            "licensed_to": "",
            "expires_on": None,
            "device_id": device_id,
        }

    licensed_to = decode_license_name(name_token)
    if not licensed_to:
        return {
            "valid": False,
            "status": "invalid",
            "message": "License owner information is invalid.",
            "license_key": key,
            "licensed_to": "",
            "expires_on": None,
            "device_id": device_id,
        }

    try:
        expiry_date = datetime.strptime(expiry_token, "%Y%m%d").date()
    except ValueError:
        return {
            "valid": False,
            "status": "invalid",
            "message": "License expiry date is invalid.",
            "license_key": key,
            "licensed_to": licensed_to,
            "expires_on": None,
            "device_id": device_id,
        }

    today = datetime.now(timezone.utc).date()
    expired = expiry_date < today
    return {
        "valid": not expired,
        "status": "expired" if expired else "active",
        "message": "License expired." if expired else "License active.",
        "license_key": key,
        "licensed_to": licensed_to,
        "expires_on": expiry_date.isoformat(),
        "device_id": device_id,
    }


def darken_hex_color(value, factor=0.22):
    color = normalize_hex_color(value)
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)

    def darken(channel):
        return max(0, min(255, int(channel * (1 - factor))))

    return f"#{darken(red):02x}{darken(green):02x}{darken(blue):02x}"


def hex_to_rgb_triplet(value):
    color = normalize_hex_color(value)
    return f"{int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}"


def theme_context():
    accent = normalize_hex_color(config.get("accent_color"), DEFAULT_ACCENT_COLOR)
    return {
        "accent_color": accent,
        "accent_color_deep": darken_hex_color(accent),
        "accent_color_rgb": hex_to_rgb_triplet(accent),
    }


def branding_context():
    return {
        "site_name": normalize_text(config.get("site_name"), DEFAULT_SITE_NAME),
        "logo_url": normalize_logo_url(config.get("logo_url")),
    }


def license_context():
    return parse_license_key(config.get("license_key"))


def license_is_valid():
    return bool(license_context()["valid"])


def ensure_license():
    license_info = license_context()
    if license_info["valid"]:
        return None
    return jsonify({"error": license_info["message"], "license": license_info}), 403


def reconcile_license_access():
    if license_is_valid():
        with USERS_LOCK:
            active_ips = list(USERS.keys())
        for ip in active_ips:
            allow_user(ip)
        return

    with USERS_LOCK:
        active_ips = list(USERS.keys())
    for ip in active_ips:
        block_user(ip)


def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as config_file:
            config.update(json.load(config_file))
    config["rate_seconds"] = normalize_rate_seconds(
        config.get("rate_seconds"),
        int(config.get("seconds_per_peso", DEFAULT_SECONDS_PER_PESO)),
    )
    config["seconds_per_peso"] = int(config["rate_seconds"]["1"])
    config["accent_color"] = normalize_hex_color(config.get("accent_color"), DEFAULT_ACCENT_COLOR)
    config["site_name"] = normalize_text(config.get("site_name"), DEFAULT_SITE_NAME)
    config["logo_url"] = normalize_logo_url(config.get("logo_url"))
    config["license_key"] = normalize_text(config.get("license_key"))
    config["device_id"] = normalize_device_id(config.get("device_id")) or generate_device_id()
    return config


def save_config():
    payload = config.copy()
    payload["seconds_per_peso"] = int(RATE_SECONDS["1"])
    payload["rate_seconds"] = {str(amount): int(RATE_SECONDS[str(amount)]) for amount in RATE_AMOUNTS}
    write_json_file(CONFIG_PATH, payload)


def write_json_file(path, payload):
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as temp_file:
        json.dump(payload, temp_file, indent=2)
    os.replace(temp_path, path)


app = Flask(__name__)
config = load_config()
app.secret_key = os.environ.get("FLASK_SECRET_KEY", config["secret_key"])

USERS_LOCK = threading.RLock()
RATE_SECONDS = {str(amount): int(config["rate_seconds"][str(amount)]) for amount in RATE_AMOUNTS}
SECONDS_PER_PESO = int(RATE_SECONDS["1"])
COIN_PENDING_SECONDS = int(config.get("coin_pending_seconds", 120))
PORTAL_IP = str(config.get("portal_ip", config.get("host", "10.0.0.1")))
PORTAL_PORT = int(config.get("portal_port", config.get("port", 80)))
save_config()


def seconds_for_pesos(pesos):
    amount = max(1, int(pesos))
    exact_rate = RATE_SECONDS.get(str(amount))
    if exact_rate is not None:
        return int(exact_rate)
    return int(RATE_SECONDS["1"]) * amount


def serialize_rates():
    return {str(amount): int(RATE_SECONDS[str(amount)]) for amount in RATE_AMOUNTS}


def portal_base_url():
    if PORTAL_PORT in (80, 443):
        return f"http://{PORTAL_IP}"
    return f"http://{PORTAL_IP}:{PORTAL_PORT}"


def portal_admin_url():
    return f"{portal_base_url()}/admin"


def get_client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    return forwarded_for or request.remote_addr or "unknown"


def save_runtime_state():
    with USERS_LOCK:
        payload = {
            "saved_at": int(time.time()),
            "users": USERS,
            "vouchers": VOUCHERS,
        }
    write_json_file(STATE_PATH, payload)


def load_runtime_state():
    if not os.path.exists(STATE_PATH):
        return {}, {}

    try:
        with open(STATE_PATH, encoding="utf-8") as state_file:
            payload = json.load(state_file)
    except (OSError, json.JSONDecodeError):
        return {}, {}

    saved_at = int(payload.get("saved_at", int(time.time())))
    elapsed = max(0, int(time.time()) - saved_at)
    restored_users = {}
    restored_vouchers = {}

    for ip, data in payload.get("users", {}).items():
        user = {
            "time": max(0, int(data.get("time", 0))),
            "pause": bool(data.get("pause", False)),
            "created_at": int(data.get("created_at", int(time.time()))),
            "waiting_for_coin": False,
            "waiting_since": None,
            "last_coin_at": data.get("last_coin_at"),
        }

        if not user["pause"]:
            user["time"] = max(0, user["time"] - elapsed)

        if user["time"] > 0:
            restored_users[ip] = user

    for raw_code, data in payload.get("vouchers", {}).items():
        code = normalize_voucher_code(raw_code)
        if not code:
            continue

        pesos = max(1, int(data.get("pesos", 1)))
        restored_vouchers[code] = {
            "code": code,
            "pesos": pesos,
            "seconds": max(seconds_for_pesos(1), int(data.get("seconds", seconds_for_pesos(pesos)))),
            "created_at": int(data.get("created_at", int(time.time()))),
            "redeemed_at": data.get("redeemed_at"),
            "redeemed_by": data.get("redeemed_by"),
        }

    return restored_users, restored_vouchers


def normalize_voucher_code(value):
    cleaned = "".join(char for char in str(value or "").upper() if char.isalnum())
    return cleaned


USERS = {}
VOUCHERS = {}
VOUCHER_CODE_LENGTH = max(6, int(config.get("voucher_code_length", 8)))
USERS, VOUCHERS = load_runtime_state()
reconcile_license_access()


def ensure_user(ip):
    with USERS_LOCK:
        if ip not in USERS:
            USERS[ip] = {
                "time": 0,
                "pause": False,
                "created_at": int(time.time()),
                "waiting_for_coin": False,
                "waiting_since": None,
                "last_coin_at": None,
            }
            if license_is_valid():
                allow_user(ip)
            save_runtime_state()
        return USERS[ip]


def serialize_user(ip, data):
    remaining = max(int(data.get("time", 0)), 0)
    waiting_since = data.get("waiting_since")
    waiting_seconds_left = 0
    if data.get("waiting_for_coin") and waiting_since:
        waiting_seconds_left = max(0, COIN_PENDING_SECONDS - (int(time.time()) - int(waiting_since)))
    return {
        "ip": ip,
        "time": remaining,
        "pause": bool(data.get("pause", False)),
        "created_at": data.get("created_at"),
        "waiting_for_coin": bool(data.get("waiting_for_coin", False)),
        "waiting_seconds_left": waiting_seconds_left,
        "coin_slot_ready": gpio_available(),
        "last_coin_at": data.get("last_coin_at"),
        "license": license_context(),
    }


def serialize_voucher(data):
    return {
        "code": data["code"],
        "pesos": int(data["pesos"]),
        "seconds": max(0, int(data.get("seconds", 0))),
        "created_at": data.get("created_at"),
        "redeemed_at": data.get("redeemed_at"),
        "redeemed_by": data.get("redeemed_by"),
        "redeemed": bool(data.get("redeemed_at")),
    }


def generate_voucher_code():
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(VOUCHER_CODE_LENGTH))
        with USERS_LOCK:
            if code not in VOUCHERS:
                return code


def is_admin():
    return bool(session.get("is_admin"))


def clear_waiting_flag(user):
    user["waiting_for_coin"] = False
    user["waiting_since"] = None


def mark_waiting(ip):
    user = ensure_user(ip)
    with USERS_LOCK:
        user["waiting_for_coin"] = True
        user["waiting_since"] = int(time.time())
        response = serialize_user(ip, user)
    save_runtime_state()
    return response


def add_coin_credit(ip):
    user = ensure_user(ip)
    with USERS_LOCK:
        user["time"] += seconds_for_pesos(1)
        user["last_coin_at"] = int(time.time())
        user["waiting_for_coin"] = True
        user["waiting_since"] = int(time.time())
        response = serialize_user(ip, user)
    save_runtime_state()
    return response


def get_waiting_client_ip():
    now = int(time.time())
    state_changed = False

    with USERS_LOCK:
        waiting_clients = []
        for ip, user in USERS.items():
            waiting_since = user.get("waiting_since")
            if not user.get("waiting_for_coin") or not waiting_since:
                continue
            if now - waiting_since > COIN_PENDING_SECONDS:
                clear_waiting_flag(user)
                state_changed = True
                continue
            waiting_clients.append((waiting_since, ip))

    if state_changed:
        save_runtime_state()

    if not waiting_clients:
        return None

    waiting_clients.sort(reverse=True)
    return waiting_clients[0][1]


def should_force_captive_redirect():
    if request.method != "GET":
        return False
    if request.path.startswith("/api/") or request.path.startswith("/static/"):
        return False
    if request.path in {"/", "/admin"}:
        return False

    host = request.host.split(":")[0].strip().lower()
    allowed_hosts = {PORTAL_IP.lower(), "127.0.0.1", "localhost"}
    return host not in allowed_hosts


@app.before_request
def captive_redirect():
    if should_force_captive_redirect():
        return redirect(portal_base_url(), code=302)
    return None


@app.route("/")
def portal():
    return render_template(
        "portal.html",
        seconds_per_peso=seconds_for_pesos(1),
        rate_seconds=serialize_rates(),
        portal_ip=PORTAL_IP,
        portal_base_url=portal_base_url(),
        **theme_context(),
        **branding_context(),
        license=license_context(),
    )


@app.route("/admin")
def admin():
    return render_template(
        "admin.html",
        authenticated=is_admin(),
        rate_seconds=serialize_rates(),
        portal_base_url=portal_base_url(),
        admin_url=portal_admin_url(),
        portal_ip=PORTAL_IP,
        **theme_context(),
        **branding_context(),
        license=license_context(),
    )


@app.route("/admin/login", methods=["POST"])
def admin_login():
    payload = request.get_json(silent=True) or request.form
    password = (payload.get("password") or "").strip()
    if password == str(config["admin_password"]):
        session["is_admin"] = True
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Invalid password."}), 401


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/redeem_voucher", methods=["POST"])
@app.route("/api/redeem_voucher", methods=["POST"])
def redeem_voucher():
    license_error = ensure_license()
    if license_error:
        return license_error

    payload = request.get_json(silent=True) or request.form
    code = normalize_voucher_code(payload.get("code"))
    if not code:
        return jsonify({"error": "Enter a voucher code."}), 400

    ip = get_client_ip()
    with USERS_LOCK:
        voucher = VOUCHERS.get(code)
        if not voucher:
            return jsonify({"error": "Voucher not found."}), 404
        if voucher.get("redeemed_at"):
            return jsonify({"error": "Voucher already used."}), 400

        user = ensure_user(ip)
        user["time"] += int(voucher["seconds"])
        user["last_coin_at"] = int(time.time())
        clear_waiting_flag(user)
        voucher["redeemed_at"] = int(time.time())
        voucher["redeemed_by"] = ip
        response = serialize_user(ip, user)
        response["voucher"] = serialize_voucher(voucher)

    save_runtime_state()
    return jsonify(response)


@app.route("/insert_coin", methods=["POST"])
@app.route("/api/insert_coin", methods=["POST"])
def insert_coin():
    license_error = ensure_license()
    if license_error:
        return license_error

    ip = get_client_ip()
    response = mark_waiting(ip)
    return jsonify(response)


@app.route("/pause", methods=["POST"])
@app.route("/api/pause", methods=["POST"])
def pause():
    license_error = ensure_license()
    if license_error:
        return license_error

    ip = get_client_ip()
    with USERS_LOCK:
        if ip in USERS:
            USERS[ip]["pause"] = True
            clear_waiting_flag(USERS[ip])
            response = serialize_user(ip, USERS[ip])
        else:
            response = None

    if response is None:
        return jsonify({"error": "No active session found."}), 404

    save_runtime_state()
    return jsonify(response)


@app.route("/resume", methods=["POST"])
@app.route("/api/resume", methods=["POST"])
def resume():
    license_error = ensure_license()
    if license_error:
        return license_error

    ip = get_client_ip()
    with USERS_LOCK:
        if ip in USERS:
            USERS[ip]["pause"] = False
            response = serialize_user(ip, USERS[ip])
        else:
            response = None

    if response is None:
        return jsonify({"error": "No active session found."}), 404

    save_runtime_state()
    return jsonify(response)


@app.route("/status")
@app.route("/api/status")
def status():
    ip = get_client_ip()
    with USERS_LOCK:
        if ip in USERS:
            return jsonify(serialize_user(ip, USERS[ip]))
    return jsonify(
        {
            "ip": ip,
            "time": 0,
            "pause": False,
            "waiting_for_coin": False,
            "waiting_seconds_left": 0,
            "coin_slot_ready": gpio_available(),
            "license": license_context(),
        }
    )


@app.route("/api/admin/clients")
def admin_clients():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    with USERS_LOCK:
        clients = [serialize_user(ip, data) for ip, data in USERS.items()]
    clients.sort(key=lambda client: client["ip"])
    return jsonify(
        {
            "clients": clients,
            "summary": {
                "active_clients": len(clients),
                "paused_clients": sum(1 for client in clients if client["pause"]),
                "waiting_clients": sum(1 for client in clients if client["waiting_for_coin"]),
                "total_minutes_left": sum(client["time"] for client in clients) // 60,
            },
        }
    )


@app.route("/api/admin/vouchers")
def admin_vouchers():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    with USERS_LOCK:
        vouchers = [serialize_voucher(data) for data in VOUCHERS.values()]

    vouchers.sort(key=lambda voucher: voucher["created_at"] or 0, reverse=True)
    return jsonify(
        {
            "vouchers": vouchers[:100],
            "summary": {
                "total_vouchers": len(vouchers),
                "unused_vouchers": sum(1 for voucher in vouchers if not voucher["redeemed"]),
                "redeemed_vouchers": sum(1 for voucher in vouchers if voucher["redeemed"]),
            },
        }
    )


@app.route("/api/admin/rates")
def admin_rates():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"rates": serialize_rates()})


@app.route("/api/admin/rates", methods=["POST"])
def admin_update_rates():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    global SECONDS_PER_PESO
    payload = request.get_json(silent=True) or {}
    raw_rates = payload.get("rates")
    if not isinstance(raw_rates, dict):
        return jsonify({"error": "Invalid rate payload."}), 400

    normalized = normalize_rate_seconds(raw_rates, RATE_SECONDS["1"])
    RATE_SECONDS.update(normalized)
    SECONDS_PER_PESO = int(RATE_SECONDS["1"])
    config["rate_seconds"] = serialize_rates()
    config["seconds_per_peso"] = int(RATE_SECONDS["1"])
    save_config()
    return jsonify({"ok": True, "rates": serialize_rates()})


@app.route("/api/admin/theme")
def admin_theme():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(theme_context())


@app.route("/api/admin/theme", methods=["POST"])
def admin_update_theme():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    accent_color = normalize_hex_color(payload.get("accent_color"), config.get("accent_color"))
    config["accent_color"] = accent_color
    save_config()
    return jsonify(theme_context())


@app.route("/api/admin/license")
def admin_license():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(license_context())


@app.route("/api/admin/license", methods=["POST"])
def admin_update_license():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    config["license_key"] = normalize_text(payload.get("license_key"))
    save_config()
    reconcile_license_access()
    return jsonify(license_context())


@app.route("/api/admin/branding")
def admin_branding():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(branding_context())


@app.route("/api/admin/branding", methods=["POST"])
def admin_update_branding():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    config["site_name"] = normalize_text(payload.get("site_name"), DEFAULT_SITE_NAME)
    config["logo_url"] = normalize_logo_url(payload.get("logo_url"))
    save_config()
    return jsonify(branding_context())


@app.route("/api/admin/vouchers", methods=["POST"])
def admin_generate_vouchers():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    license_error = ensure_license()
    if license_error:
        return license_error

    payload = request.get_json(silent=True) or {}
    pesos = max(1, int(payload.get("pesos", 1)))
    count = max(1, min(int(payload.get("count", 1)), 100))
    now = int(time.time())
    created = []

    with USERS_LOCK:
        for _ in range(count):
            code = generate_voucher_code()
            voucher = {
                "code": code,
                "pesos": pesos,
                "seconds": seconds_for_pesos(pesos),
                "created_at": now,
                "redeemed_at": None,
                "redeemed_by": None,
            }
            VOUCHERS[code] = voucher
            created.append(serialize_voucher(voucher))

    save_runtime_state()
    return jsonify({"created": created})


@app.route("/api/admin/voucher/<code>", methods=["DELETE"])
def admin_delete_voucher(code):
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    normalized_code = normalize_voucher_code(code)
    with USERS_LOCK:
        voucher = VOUCHERS.get(normalized_code)
        if not voucher:
            return jsonify({"error": "Voucher not found."}), 404
        if voucher.get("redeemed_at"):
            return jsonify({"error": "Redeemed vouchers cannot be deleted."}), 400
        VOUCHERS.pop(normalized_code, None)

    save_runtime_state()
    return jsonify({"ok": True})


@app.route("/api/admin/client/<path:ip>/toggle_pause", methods=["POST"])
def admin_toggle_pause(ip):
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    with USERS_LOCK:
        user = USERS.get(ip)
        if not user:
            return jsonify({"error": "Client not found."}), 404
        user["pause"] = not user["pause"]
        response = serialize_user(ip, user)

    save_runtime_state()
    return jsonify(response)


@app.route("/api/admin/client/<path:ip>/add_time", methods=["POST"])
def admin_add_time(ip):
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    license_error = ensure_license()
    if license_error:
        return license_error

    payload = request.get_json(silent=True) or {}
    pesos = max(int(payload.get("pesos", 1)), 1)

    with USERS_LOCK:
        user = ensure_user(ip)
        user["time"] += seconds_for_pesos(pesos)
        response = serialize_user(ip, user)

    save_runtime_state()
    return jsonify(response)


@app.route("/api/admin/client/<path:ip>", methods=["DELETE"])
def admin_disconnect(ip):
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401

    with USERS_LOCK:
        user = USERS.pop(ip, None)

    if not user:
        return jsonify({"error": "Client not found."}), 404

    block_user(ip)
    save_runtime_state()
    return jsonify({"ok": True})


@app.route("/generate_204")
@app.route("/redirect")
@app.route("/hotspot-detect.html")
@app.route("/canonical.html")
@app.route("/success.txt")
@app.route("/ncsi.txt")
@app.route("/connecttest.txt")
@app.route("/library/test/success.html")
def captive_probe():
    return redirect(portal_base_url(), code=302)


def timer():
    last_license_valid = license_is_valid()
    while True:
        time.sleep(1)
        expired_ips = []
        state_changed = False
        current_license_valid = license_is_valid()

        if current_license_valid != last_license_valid:
            reconcile_license_access()
            last_license_valid = current_license_valid

        with USERS_LOCK:
            for ip, user in list(USERS.items()):
                if user.get("waiting_for_coin") and user.get("waiting_since"):
                    if int(time.time()) - user["waiting_since"] > COIN_PENDING_SECONDS:
                        clear_waiting_flag(user)
                        state_changed = True

                if user.get("time", 0) <= 0:
                    continue
                if user.get("pause"):
                    continue

                user["time"] -= 1
                state_changed = True
                if user["time"] <= 0:
                    expired_ips.append(ip)

            for ip in expired_ips:
                USERS.pop(ip, None)
                state_changed = True

        for ip in expired_ips:
            block_user(ip)

        if state_changed:
            save_runtime_state()


threading.Thread(target=timer, daemon=True).start()


def coin_listener():
    if not gpio_available():
        return

    while True:
        try:
            wait_coin()
            waiting_ip = get_waiting_client_ip()
            if waiting_ip:
                add_coin_credit(waiting_ip)
        except Exception:
            time.sleep(1)


threading.Thread(target=coin_listener, daemon=True).start()


if __name__ == "__main__":
    bind_host = str(config.get("host", PORTAL_IP))
    bind_port = int(config.get("port", PORTAL_PORT))
    debug_enabled = bool(config.get("debug", False))

    try:
        app.run(host=bind_host, port=bind_port, debug=debug_enabled)
    except OSError as error:
        if "not valid in its context" not in str(error):
            raise

        fallback_host = "0.0.0.0"
        print(
            f"Configured host {bind_host} is not assigned on this machine. "
            f"Falling back to {fallback_host}:{bind_port}."
        )
        app.run(host=fallback_host, port=bind_port, debug=debug_enabled)
