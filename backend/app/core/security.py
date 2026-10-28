"""Password hashing (Argon2id) and session tokens."""

import hashlib
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128

# argon2-cffi's defaults are Argon2id with parameters from RFC 9106's recommendations.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@lru_cache
def _dummy_hash() -> str:
    return _hasher.hash(secrets.token_urlsafe(16))


def burn_verification_time(password: str) -> None:
    """Spend the same time as a real check, so response timing does not reveal whether a
    username exists."""
    verify_password(_dummy_hash(), password)


def password_problems(password: str, username: str | None = None) -> list[str]:
    problems = []
    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append(f"must be at most {MAX_PASSWORD_LENGTH} characters")
    if username and username.lower() in password.lower():
        problems.append("must not contain the username")
    if password and len(set(password)) < 4:
        problems.append("must contain at least 4 different characters")
    return problems


def new_session_token() -> tuple[str, str]:
    """Return (token for the cookie, SHA-256 hex digest for the database)."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
