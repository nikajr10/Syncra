"""Passwords and login tokens.

Passwords are hashed with scrypt (Python's hashlib). Login tokens are random; only their SHA-256
is stored (`auth_tokens`), so a copy of the database holds no usable logins.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 5  # OWASP's scrypt minimum: 16 MiB per hash
NO_HASH = f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${'0' * 32}${'0' * 128}"  # matches nothing


def hash_password(password: str) -> str:
    """`scrypt$n$r$p$salt$hash`: the parameters travel with the hash, so they can be raised."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    """Hashes even when there is no stored hash, so timing doesn't tell which usernames exist."""
    _, n, r, p, salt, digest = (stored or NO_HASH).split("$")
    test = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
    return stored is not None and hmac.compare_digest(test.hex(), digest)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
