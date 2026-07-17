"""User model.

See docs/data-model.md for the schema as a whole and the reasoning behind it.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # Stored lowercase — see normalise_email(). Ion@x.md and ion@x.md are the
    # same person, and letting both register creates an account nobody can log
    # into.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    # Deactivate rather than delete: a deleted user orphans their orders, and
    # an order without a buyer is a broken receipt.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    # server_default, not a Python default: the database clock is the one
    # authority every writer shares.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"


def normalise_email(email: str) -> str:
    """Canonical form for storage and lookup.

    The single place this happens. The unique constraint only prevents
    duplicates of the *same* string, so if any caller skips this, duplicates
    that differ by case get in and the constraint never fires.

    Only case and surrounding whitespace are touched. Gmail's dot and plus
    rules are deliberately not applied: they are provider-specific, and
    treating ion.popescu@ and ionpopescu@ as one account would be wrong for
    every provider that does not work that way.
    """
    return email.strip().lower()
