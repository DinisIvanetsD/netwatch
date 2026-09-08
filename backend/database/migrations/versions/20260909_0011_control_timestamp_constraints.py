"""Enforce required timestamps for control records.

Revision ID: 20260909_0011
Revises: 20260908_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0011"
down_revision: str | None = "20260908_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIMESTAMP_COLUMNS = {
    "control_profiles": ("created_at", "updated_at"),
    "domain_rules": ("created_at",),
    "access_audit": ("created_at",),
}


def upgrade() -> None:
    for table_name, columns in _TIMESTAMP_COLUMNS.items():
        for column_name in columns:
            op.execute(
                sa.text(
                    f"UPDATE {table_name} SET {column_name} = CURRENT_TIMESTAMP "
                    f"WHERE {column_name} IS NULL"
                )
            )
        with op.batch_alter_table(table_name) as batch:
            for column_name in columns:
                batch.alter_column(
                    column_name,
                    existing_type=sa.DateTime(timezone=True),
                    existing_server_default=sa.text("CURRENT_TIMESTAMP"),
                    nullable=False,
                )


def downgrade() -> None:
    for table_name, columns in reversed(tuple(_TIMESTAMP_COLUMNS.items())):
        with op.batch_alter_table(table_name) as batch:
            for column_name in columns:
                batch.alter_column(
                    column_name,
                    existing_type=sa.DateTime(timezone=True),
                    existing_server_default=sa.text("CURRENT_TIMESTAMP"),
                    nullable=True,
                )
