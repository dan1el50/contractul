"""Authentication logic against a real database.

No HTTP here — the service knows nothing about it. These tests target the
security properties, because auth is where a green suite most easily hides a
real hole.
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session
from app.models.user import User
from app.services import auth as auth_service

PASSWORD = "parola-mea-sigura-2026"


async def _register(session: AsyncSession, email: str = "ion@nordconstruct.md") -> User:
    return await auth_service.register(
        session, email=email, password=PASSWORD, full_name="Ion Popescu"
    )


# ─── Registration ────────────────────────────────────────────────────────────


async def test_register_creates_a_user(session: AsyncSession) -> None:
    user = await _register(session)

    assert user.id is not None
    assert user.email == "ion@nordconstruct.md"


async def test_register_never_stores_the_plaintext_password(session: AsyncSession) -> None:
    user = await _register(session)

    assert user.password_hash != PASSWORD
    assert PASSWORD not in user.password_hash


async def test_register_normalises_the_email(session: AsyncSession) -> None:
    user = await _register(session, email="  Ion@NordConstruct.MD  ")

    assert user.email == "ion@nordconstruct.md"


async def test_register_rejects_a_duplicate_email(session: AsyncSession) -> None:
    await _register(session)

    with pytest.raises(auth_service.EmailAlreadyRegistered):
        await _register(session)


async def test_register_rejects_a_duplicate_differing_only_by_case(session: AsyncSession) -> None:
    await _register(session, email="ion@nordconstruct.md")

    with pytest.raises(auth_service.EmailAlreadyRegistered):
        await _register(session, email="ION@NORDCONSTRUCT.MD")


async def test_new_users_are_not_admins(session: AsyncSession) -> None:
    """Registration must never be a path to privilege."""
    user = await _register(session)

    assert user.is_admin is False


# ─── Authentication ──────────────────────────────────────────────────────────


async def test_authenticate_accepts_correct_credentials(session: AsyncSession) -> None:
    await _register(session)

    user = await auth_service.authenticate(
        session, email="ion@nordconstruct.md", password=PASSWORD
    )

    assert user.email == "ion@nordconstruct.md"


async def test_authenticate_is_case_insensitive_on_email(session: AsyncSession) -> None:
    await _register(session)

    user = await auth_service.authenticate(
        session, email="ION@NordConstruct.md", password=PASSWORD
    )

    assert user.id is not None


async def test_authenticate_rejects_a_wrong_password(session: AsyncSession) -> None:
    await _register(session)

    with pytest.raises(auth_service.InvalidCredentials):
        await auth_service.authenticate(
            session, email="ion@nordconstruct.md", password="parola-gresita-123"
        )


async def test_authenticate_rejects_an_unknown_email(session: AsyncSession) -> None:
    with pytest.raises(auth_service.InvalidCredentials):
        await auth_service.authenticate(session, email="nimeni@nicaieri.md", password=PASSWORD)


async def test_authenticate_rejects_a_deactivated_user(session: AsyncSession) -> None:
    """Correct password, deactivated account — still refused."""
    user = await _register(session)
    user.is_active = False
    await session.flush()

    with pytest.raises(auth_service.InvalidCredentials):
        await auth_service.authenticate(
            session, email="ion@nordconstruct.md", password=PASSWORD
        )


async def test_all_authentication_failures_raise_the_same_exception(
    session: AsyncSession,
) -> None:
    """Account enumeration guard.

    Unknown email, wrong password, and deactivated account must be
    indistinguishable to a caller — so the API cannot leak which it was even
    if a future handler tries to be helpful.
    """
    user = await _register(session, email="active@nordconstruct.md")
    user.is_active = False
    await session.flush()

    failures = []
    for email, password in [
        ("unknown@nowhere.md", PASSWORD),
        ("active@nordconstruct.md", "wrong-password-here"),
        ("active@nordconstruct.md", PASSWORD),
    ]:
        with pytest.raises(auth_service.InvalidCredentials) as exc:
            await auth_service.authenticate(session, email=email, password=password)
        failures.append(str(exc.value))

    assert len(set(failures)) == 1


# ─── Sessions ────────────────────────────────────────────────────────────────


async def test_create_session_returns_a_token_that_resolves(session: AsyncSession) -> None:
    user = await _register(session)

    token = await auth_service.create_session(session, user=user)
    resolved = await auth_service.resolve_session(session, token=token)

    assert resolved is not None
    assert resolved.id == user.id


async def test_the_raw_token_is_never_stored(session: AsyncSession) -> None:
    """The database holds a hash. A dump must not yield working sessions."""
    user = await _register(session)
    token = await auth_service.create_session(session, user=user)

    record = await session.scalar(select(Session).where(Session.user_id == user.id))

    assert record is not None
    assert record.token_hash != token
    assert len(record.token_hash) == 64


async def test_an_unknown_token_resolves_to_nothing(session: AsyncSession) -> None:
    assert await auth_service.resolve_session(session, token="made-up-token") is None


async def test_an_expired_session_resolves_to_nothing(session: AsyncSession) -> None:
    user = await _register(session)
    token = await auth_service.create_session(session, user=user)

    record = await session.scalar(select(Session).where(Session.user_id == user.id))
    assert record is not None
    record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await session.flush()

    assert await auth_service.resolve_session(session, token=token) is None


async def test_a_revoked_session_resolves_to_nothing(session: AsyncSession) -> None:
    user = await _register(session)
    token = await auth_service.create_session(session, user=user)

    await auth_service.revoke_session(session, token=token)

    assert await auth_service.resolve_session(session, token=token) is None


async def test_deactivating_a_user_kills_their_live_session(session: AsyncSession) -> None:
    """The entire reason sessions are server-side rather than JWT.

    A stateless token would keep working until it expired, no matter what the
    database said.
    """
    user = await _register(session)
    token = await auth_service.create_session(session, user=user)
    assert await auth_service.resolve_session(session, token=token) is not None

    user.is_active = False
    await session.flush()

    assert await auth_service.resolve_session(session, token=token) is None


async def test_revoking_one_session_leaves_others_alone(session: AsyncSession) -> None:
    """Signing out of one device must not sign you out everywhere."""
    user = await _register(session)
    phone = await auth_service.create_session(session, user=user)
    laptop = await auth_service.create_session(session, user=user)

    await auth_service.revoke_session(session, token=phone)

    assert await auth_service.resolve_session(session, token=phone) is None
    assert await auth_service.resolve_session(session, token=laptop) is not None


async def test_revoking_an_unknown_token_is_silent(session: AsyncSession) -> None:
    """Logout is idempotent."""
    await auth_service.revoke_session(session, token="never-existed")


async def test_sessions_are_unique_per_login(session: AsyncSession) -> None:
    user = await _register(session)

    assert await auth_service.create_session(session, user=user) != (
        await auth_service.create_session(session, user=user)
    )
