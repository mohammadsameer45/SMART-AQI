"""
generate_vapid_keys.py  -  one-off VAPID keypair generator for Web Push
threshold alerts. Prints backend/.env-ready lines; run once per install and
paste the output into backend/.env (never commit real keys).

Usage:  python scripts/generate_vapid_keys.py
"""
from __future__ import annotations

import base64

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid02


def main() -> None:
    v = Vapid02()
    v.generate_keys()

    priv_pem = v.private_pem().decode()
    priv_oneline = "\\n".join(priv_pem.splitlines())

    pub_raw = v.public_key.public_bytes(
        encoding=Encoding.X962, format=PublicFormat.UncompressedPoint)
    pub_b64url = base64.urlsafe_b64encode(pub_raw).rstrip(b"=").decode()

    print("Paste into backend/.env:\n")
    print(f"VAPID_PRIVATE_KEY_PEM={priv_oneline}")
    print(f"VAPID_PUBLIC_KEY={pub_b64url}")
    print("VAPID_SUBJECT=mailto:you@example.com  # change to a real contact")


if __name__ == "__main__":
    main()
