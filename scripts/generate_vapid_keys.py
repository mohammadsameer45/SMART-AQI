"""
generate_vapid_keys.py  -  one-off VAPID keypair generator for Web Push
threshold alerts. Prints backend/.env-ready lines; run once per install and
paste the output into backend/.env (never commit real keys).

Both keys are raw base64url (no padding) — the format pywebpush's
Vapid.from_string() expects for the private key (it auto-detects RAW vs DER
by decoded length; a PEM string does NOT work here, since a PEM's
"-----BEGIN...-----" header isn't valid base64), and the format the
browser's PushManager.subscribe() applicationServerKey expects for the
public key.

Usage:  python scripts/generate_vapid_keys.py
"""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid02


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def main() -> None:
    v = Vapid02()
    v.generate_keys()

    priv_int = v.private_key.private_numbers().private_value
    priv_raw = priv_int.to_bytes(32, "big")

    pub_raw = v.public_key.public_bytes(
        encoding=Encoding.X962, format=PublicFormat.UncompressedPoint)

    print("Paste into backend/.env:\n")
    print(f"VAPID_PRIVATE_KEY={b64url(priv_raw)}")
    print(f"VAPID_PUBLIC_KEY={b64url(pub_raw)}")
    print("VAPID_SUBJECT=mailto:you@example.com  # change to a real contact")


if __name__ == "__main__":
    main()
