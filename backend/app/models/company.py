"""Company model: the buyer's company details, for contracts and records.

One per user, optional — the buyer may be an individual. See docs/data-model.md
for why this is a separate table rather than nullable columns on `users`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    # UNIQUE makes it one-to-one: a user has at most one company.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # The Moldovan company identifier — exactly 13 digits. The database enforces
    # the shape it can (length); the schema enforces that they are digits.
    idno: Mapped[str] = mapped_column(String(13), nullable=False)

    legal_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    iban: Mapped[str | None] = mapped_column(String(34), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (CheckConstraint("char_length(idno) = 13", name="idno_length"),)

    def __repr__(self) -> str:
        return f"<Company {self.name!r} idno={self.idno}>"
