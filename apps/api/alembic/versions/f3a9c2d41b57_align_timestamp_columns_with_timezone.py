"""align timestamp columns with timezone

Revision ID: f3a9c2d41b57
Revises: aaa30108dfdb
Create Date: 2026-09-22

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a9c2d41b57"
down_revision: str | Sequence[str] | None = "aaa30108dfdb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = {
    "users": ["created_at"],
    "projects": ["created_at", "updated_at"],
    "refresh_tokens": ["expires_at", "revoked_at", "created_at"],
}


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    """Store timestamps as UTC-aware (TIMESTAMP WITH TIME ZONE)."""
    if _is_sqlite():
        # SQLite stores datetimes as naive text and has no ALTER COLUMN; nothing to do.
        return
    for table, columns in _TABLES.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                type_=sa.DateTime(timezone=True),
                existing_type=sa.DateTime(),
                postgresql_using=f"{column} AT TIME ZONE 'UTC'",
            )


def downgrade() -> None:
    """Revert timestamps to naive UTC."""
    if _is_sqlite():
        return
    for table, columns in _TABLES.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                type_=sa.DateTime(),
                existing_type=sa.DateTime(timezone=True),
                postgresql_using=f"{column} AT TIME ZONE 'UTC'",
            )
