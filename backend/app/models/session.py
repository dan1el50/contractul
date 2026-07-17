"""Session model.

Sessions are server-side rather than stateless tokens (JWT). The deciding
factor is revocation: deactivating an account, or logging out, must take effect
immediately. A JWT stays valid until it expires no matter what the database
says, and the usual fix — a revocation list — is a sessions table with extra
steps.

The cost is one indexed lookup per authenticated request, which at this scale
is nothing.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # SHA-256 of the token, never the token. See core.security.hash_session_token.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    # CASCADE: a deleted user's sessions are meaningless. This is the one place
    # cascade is right — everywhere else in the schema, history outlives its
    # subject and deletes are soft.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Set on logout. Nullable rather than a boolean so that *when* is recorded
    # too — useful when someone reports an account they did not sign out of.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # Every authenticated request filters on exactly this pair, and it is
        # the hottest query in the system once people are logged in.
        Index("ix_sessions_user_id_expires_at", "user_id", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<Session user={self.user_id} expires={self.expires_at:%Y-%m-%d}>"
