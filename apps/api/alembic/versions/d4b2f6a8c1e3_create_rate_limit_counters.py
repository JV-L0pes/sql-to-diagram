"""create rate limit counters

Revision ID: d4b2f6a8c1e3
Revises: c8d1e7f2a9b4
Create Date: 2026-09-22

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4b2f6a8c1e3"
down_revision: str | Sequence[str] | None = "c8d1e7f2a9b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Fixed-window rate limit counters shared by all serverless instances."""
    op.create_table(
        "rate_limit_counters",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("window_start", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_counters")
