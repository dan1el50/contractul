"""add sessions table

Revision ID: 0003_sessions
Revises: 0002_users
Created: phase 3, authentication

Reviewed by hand after autogenerate. One new table, no data to lose, no
renames — nothing hiding as a drop-and-add.

See docs/data-model.md for why sessions are server-side rather than JWT.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_sessions"
down_revision: str | None = "0002_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        # 64 = length of a hex SHA-256 digest. Holds the hash, never the token.
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_sessions_user_id_users"),
            # The only CASCADE in the schema. A deleted user's sessions are
            # meaningless; elsewhere history outlives its subject.
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    op.create_index(
        "ix_sessions_user_id_expires_at",
        "sessions",
        ["user_id", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_user_id_expires_at", table_name="sessions")
    op.drop_table("sessions")
