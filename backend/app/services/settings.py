"""Account settings: profile, password, and company details.

No HTTP here, like every service. The password path deliberately reaches into
the session store — changing a password ends every other session.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.company import Company
from app.models.user import User
from app.services import auth as auth_service


class IncorrectPassword(Exception):
    """The current password given on a change did not match."""


async def update_profile(
    session: AsyncSession, *, user: User, full_name: str, phone: str | None
) -> User:
    """Update the mutable profile fields. Email is not among them — changing a
    login identity is a separate, weightier operation than editing a name."""
    user.full_name = full_name.strip()
    user.phone = phone.strip() if phone else None
    await session.flush()
    return user


async def change_password(
    session: AsyncSession,
    *,
    user: User,
    current_password: str,
    new_password: str,
    keep_token: str | None,
) -> None:
    """Verify the current password, set the new one, and end other sessions.

    Requiring the current password means a stolen but still-open session cannot
    quietly change the password and lock the owner out. Revoking the other
    sessions afterwards means that if one already had, this takes their access
    away the moment the real owner acts.
    """
    if not verify_password(current_password, user.password_hash):
        raise IncorrectPassword()

    user.password_hash = hash_password(new_password)
    await session.flush()
    await auth_service.revoke_other_sessions(session, user_id=user.id, keep_token=keep_token)


async def get_company(session: AsyncSession, *, user_id: uuid.UUID) -> Company | None:
    company: Company | None = await session.scalar(
        select(Company).where(Company.user_id == user_id)
    )
    return company


async def upsert_company(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    name: str,
    idno: str,
    legal_address: str | None,
    iban: str | None,
    bank_name: str | None,
) -> Company:
    """Create or update the user's single company record."""
    company = await get_company(session, user_id=user_id)
    if company is None:
        company = Company(user_id=user_id)
        session.add(company)

    company.name = name.strip()
    company.idno = idno
    company.legal_address = legal_address.strip() if legal_address else None
    company.iban = iban.strip() if iban else None
    company.bank_name = bank_name.strip() if bank_name else None

    await session.flush()
    return company
