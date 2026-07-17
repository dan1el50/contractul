"""The User model against a real PostgreSQL.

Proves the ORM mapping matches the schema and that the constraints bite. A
model can map to the wrong column name and every unit test still passes —
only the database catches that.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, normalise_email


async def _add_user(session: AsyncSession, email: str, **overrides: object) -> User:
    user = User(
        email=normalise_email(email),
        password_hash="not-a-real-hash",
        full_name="Ion Popescu",
        **overrides,
    )
    session.add(user)
    await session.flush()
    return user


async def test_user_can_be_persisted_and_read_back(session: AsyncSession) -> None:
    await _add_user(session, "ion@nordconstruct.md")

    found = await session.scalar(select(User).where(User.email == "ion@nordconstruct.md"))

    assert found is not None
    assert found.full_name == "Ion Popescu"


async def test_server_defaults_are_applied(session: AsyncSession) -> None:
    """id, timestamps and flags come from the database, not from Python."""
    user = await _add_user(session, "defaults@nordconstruct.md")
    await session.refresh(user)

    assert user.id is not None
    assert user.created_at is not None
    assert user.updated_at is not None
    assert user.is_admin is False
    assert user.is_active is True


async def test_timestamps_are_timezone_aware(session: AsyncSession) -> None:
    """TIMESTAMPTZ, not TIMESTAMP.

    A naive timestamp is ambiguous twice a year in Moldova, when the clocks
    go back and the same wall-clock hour happens twice.
    """
    user = await _add_user(session, "tz@nordconstruct.md")
    await session.refresh(user)

    assert user.created_at.tzinfo is not None


async def test_duplicate_email_is_rejected(session: AsyncSession) -> None:
    await _add_user(session, "duplicate@nordconstruct.md")

    with pytest.raises(IntegrityError, match="uq_users_email"):
        await _add_user(session, "duplicate@nordconstruct.md")


async def test_emails_differing_only_by_case_collide(session: AsyncSession) -> None:
    """The constraint plus normalisation together are what prevent this.

    The constraint alone would happily store both, because as raw strings they
    differ — which is exactly why normalise_email must not be bypassed.
    """
    await _add_user(session, "Ion@NordConstruct.md")

    with pytest.raises(IntegrityError, match="uq_users_email"):
        await _add_user(session, "ION@nordconstruct.MD")


async def test_phone_is_optional(session: AsyncSession) -> None:
    """Not every buyer is a company with a switchboard."""
    user = await _add_user(session, "nophone@nordconstruct.md")
    await session.refresh(user)

    assert user.phone is None


async def test_admin_flag_can_be_set(session: AsyncSession) -> None:
    user = await _add_user(session, "admin@crowe.md", is_admin=True)
    await session.refresh(user)

    assert user.is_admin is True


async def test_tests_do_not_leak_into_each_other(session: AsyncSession) -> None:
    """The rollback fixture is load-bearing.

    Every test above inserts users. If any of them survived, this would fail —
    and the suite would start depending on execution order.
    """
    count = len((await session.scalars(select(User))).all())

    assert count == 0
