import argparse
import base64
import hashlib
import hmac
import sys
from datetime import datetime


LICENSE_PREFIX = "PWF1"
LICENSE_SIGNATURE_LENGTH = 12
LICENSE_SIGNING_SECRET = "piso-wifi-license-v1"
DEVICE_ID_LENGTH = 12


def normalize_text(value):
    return " ".join(str(value or "").split()).strip()


def normalize_device_id(value):
    cleaned = "".join(char for char in str(value or "").upper() if char.isalnum())
    return cleaned[:DEVICE_ID_LENGTH]


def encode_name(name):
    encoded = base64.urlsafe_b64encode(name.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def build_license_key(name, expiry, device_id):
    normalized_name = normalize_text(name)
    normalized_device_id = normalize_device_id(device_id)

    if not normalized_name:
        raise ValueError("Name is required.")
    if len(normalized_device_id) != DEVICE_ID_LENGTH:
        raise ValueError(f"Device ID must be {DEVICE_ID_LENGTH} alphanumeric characters.")

    datetime.strptime(expiry, "%Y%m%d")

    name_token = encode_name(normalized_name)
    signature = hmac.new(
        LICENSE_SIGNING_SECRET.encode("utf-8"),
        f"{expiry}:{name_token}:{normalized_device_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:LICENSE_SIGNATURE_LENGTH]

    return f"{LICENSE_PREFIX}-{expiry}-{name_token}-{normalized_device_id}-{signature}"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate a device-bound Piso WiFi license key."
    )
    parser.add_argument("--name", required=True, help="Licensed owner or business name.")
    parser.add_argument(
        "--expiry",
        required=True,
        help="Expiry date in YYYYMMDD format, for example 20991231.",
    )
    parser.add_argument(
        "--device-id",
        required=True,
        help="Target device ID from the admin license screen.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        license_key = build_license_key(args.name, args.expiry, args.device_id)
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print("License key:")
    print(license_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
