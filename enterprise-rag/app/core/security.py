"""Password hashing primitives for user credentials."""

import hashlib
import hmac
import secrets


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a unique salt."""
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded_hash: str | None) -> bool:
    """Constant-time verification of a stored PBKDF2 password hash."""
    if not encoded_hash:
        return False
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)
        )
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (ValueError, TypeError):
        return False
