import hashlib
import hmac
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from pydantic import SecretStr

HASHER = PasswordHasher()
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_-]{43}")


def password_matches(encoded: str, password: SecretStr) -> bool:
    try:
        return HASHER.verify(encoded, password.get_secret_value())
    except VerificationError, InvalidHashError:
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def csrf_for(token: str) -> str:
    # Separate proof of possession for the browser; never return the HttpOnly session secret.
    return hmac.new(token.encode(), b"iphi/session/csrf/v1", hashlib.sha256).hexdigest()


def csrf_matches(token: str, supplied: str) -> bool:
    return (
        len(supplied) == 64
        and supplied.isascii()
        and hmac.compare_digest(csrf_for(token), supplied)
    )
