"""Password hashing and session tokens.

The cryptographic primitives, isolated from any business logic. Nothing here
knows what a user is.
"""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# Defaults are argon2-cffi's, which track the OWASP guidance. Raising them is
# a deliberate operation, not a tweak: the parameters are baked into every hash
# ever written, so a change only affects new passwords and existing users stay
# on the old cost until they next log in.
_hasher = PasswordHasher()

# 32 bytes from the OS CSPRNG. This is the entire secret protecting a logged-in
# account, so it must be unguessable — never uuid4(), never anything seeded from
# a clock.
SESSION_TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    """Argon2id hash, salt included in the output string."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time check. False on any failure, never an exception.

    A caller that has to distinguish "wrong password" from "corrupt hash" would
    leak that difference to whoever is guessing.
    """
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when a hash was made with parameters weaker than today's.

    Lets us upgrade a user's hash transparently on their next successful login,
    which is the only moment the plaintext is available.
    """
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, ValueError):
        return False


def generate_session_token() -> str:
    """A fresh opaque session token. Returned to the client, never stored."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """What actually goes in the database.

    Sessions are stored hashed for the same reason passwords are: someone who
    reads the sessions table must not be able to use what they find. Anyone
    with a database dump would otherwise hold a working login for every user
    currently signed in.

    Plain SHA-256, not Argon2, and deliberately so. Argon2 is slow by design to
    frustrate guessing a low-entropy human password. A session token is 32
    random bytes — guessing is already impossible — and this runs on every
    authenticated request, so slowness would buy nothing and cost everything.
    """
    return hashlib.sha256(token.encode()).hexdigest()
