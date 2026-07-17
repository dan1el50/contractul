"""Baseline — establishes the migration chain.

Revision ID: 0001_baseline
Revises:
Created: phase 0, walking skeleton

Intentionally empty. This migration creates no tables; it exists so that the
chain has a root and so that `alembic upgrade head` produces the
alembic_version row the health check reads.

The real schema arrives in phase 2. See docs/roadmap.md.
"""

from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
