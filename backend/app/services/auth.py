"""Authentication logic.

Knows nothing about HTTP — no requests, no cookies, no status codes. That is
what makes it testable without a web server, and it is the pattern every other
service in this codebase follows.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    needs_rehash,
    verify_password,
)
from app.models.session import Session
from app.models.user import User, normalise_email

logger = logging.getLogger(__name__)

SESSION_LIFETIME = timedelta(days=30)

# Argon2 hash of nothing in particular, used to burn the same CPU time on a
# missing user as on a real one. See authenticate().
_DUMMY_HASH = hash_password("this-is-never-a-real-password")


class EmailAlreadyRegistered(Exception):
    """Raised on registering an email that already exists."""


class InvalidCredentials(Exception):
    """Wrong email, wrong password, or a deactivated account.

    Deliberately one exception for all three. Callers cannot accidentally tell
    an attacker which of them it was.
    """


async def register(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str,
    phone: str | None = None,
) -> User:
    """Create a user. Raises EmailAlreadyRegistered if the email is taken."""
    user = User(
        email=normalise_email(email),
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        phone=phone.strip() if phone else None,
    )
    session.add(user)

    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        # Let the database decide, rather than checking first. A SELECT then an
        # INSERT is a race: two simultaneous registrations both see nothing and
        # both proceed. The unique constraint cannot be raced.
        raise EmailAlreadyRegistered(email) from exc

    logger.info("Registered user %s", user.id)
    return user


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
    """Verify credentials. Raises InvalidCredentials on any failure."""
    user = await session.scalar(select(User).where(User.email == normalise_email(email)))

    if user is None:
        # Hash anyway. Otherwise a missing user returns in microseconds while a
        # real one takes ~50ms of Argon2, and that gap is a reliable oracle for
        # discovering which emails have accounts — worth having for a platform
        # whose customers are identifiable companies.
        verify_password(password, _DUMMY_HASH)
        raise InvalidCredentials

    if not verify_password(password, user.password_hash):
        raise InvalidCredentials

    if not user.is_active:
        # Checked after the password, so a deactivated account is
        # indistinguishable from a wrong password to anyone probing.
        raise InvalidCredentials

    if needs_rehash(user.password_hash):
        # The only moment the plaintext exists, so the only moment an upgrade
        # is possible.
        user.password_hash = hash_password(password)
        logger.info("Upgraded password hash for user %s", user.id)

    return user


async def create_session(session: AsyncSession, *, user: User) -> str:
    """Open a session and return the raw token.

    The token is returned once and never stored — only its hash goes to the
    database. If the caller loses it, it is gone.
    """
    token = generate_session_token()

    session.add(
        Session(
            token_hash=hash_session_token(token),
            user_id=user.id,
            expires_at=datetime.now(UTC) + SESSION_LIFETIME,
        )
    )
    await session.flush()

    return token


async def resolve_session(session: AsyncSession, *, token: str) -> User | None:
    """The user behind a session token, or None if it does not grant access.

    None covers every failure — unknown, expired, revoked, deactivated — because
    the caller's response to all of them is identical.
    """
    record = await session.scalar(
        select(Session).where(Session.token_hash == hash_session_token(token))
    )

    if record is None or record.revoked_at is not None:
        return None

    # Checked in Python, not SQL, so that expiry is decided by one clock rather
    # than depending on which of the two is right.
    if record.expires_at <= datetime.now(UTC):
        return None

    user = await session.get(User, record.user_id)

    # is_active is re-read on every request — that is the entire reason for
    # server-side sessions. Deactivating an account logs them out now, not
    # whenever a token would have expired.
    if user is None or not user.is_active:
        return None

    return user


async def revoke_session(session: AsyncSession, *, token: str) -> None:
    """End a session. Silent if the token is unknown — logout is idempotent."""
    record = await session.scalar(
        select(Session).where(Session.token_hash == hash_session_token(token))
    )

    if record is not None and record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        await session.flush()
