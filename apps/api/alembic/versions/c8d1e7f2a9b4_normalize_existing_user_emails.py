"""normalize existing user emails to lowercase

Revision ID: c8d1e7f2a9b4
Revises: f3a9c2d41b57
Create Date: 2026-09-22

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d1e7f2a9b4"
down_revision: str | Sequence[str] | None = "f3a9c2d41b57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rows written before email normalization could bypass the unique index by casing."""
    op.execute("UPDATE users SET email = lower(email) WHERE email <> lower(email)")


def downgrade() -> None:
    # The original casing is not recoverable; nothing to reverse.
    pass
