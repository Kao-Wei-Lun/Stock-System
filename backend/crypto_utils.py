from __future__ import annotations

import base64
import os
from functools import lru_cache

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


_SALT = b"quantvision-fubon-salt-v1"


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    raw_key = os.environ.get("APP_ENCRYPT_KEY", "").strip()
    if not raw_key:
        raise RuntimeError(
            "APP_ENCRYPT_KEY is not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=100_000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(raw_key.encode("utf-8")))
    return Fernet(key)


def encrypt_field(plaintext: str | None) -> str:
    if not plaintext:
        return ""
    return _get_fernet().encrypt(str(plaintext).encode("utf-8")).decode("utf-8")


def decrypt_field(ciphertext: str | None) -> str:
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(str(ciphertext).encode("utf-8")).decode("utf-8")
    except Exception:
        return ""
