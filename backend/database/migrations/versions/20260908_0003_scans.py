"""Create scans table.

Revision ID: 20260908_0003
Revises: 20260908_0002
Create Date: 2026-09-08 00:20:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0003"
down_revision: str | None = "20260908_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "RUNNING",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                name="scanstatus",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("devices_found", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("subnet", sa.String(length=45), nullable=False),
        sa.Column(
            "source",
            sa.Enum("LIVE", "DEMO", name="devicesource", native_enum=False, length=16),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scans")),
    )
    op.create_index(op.f("ix_scans_status"), "scans", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_scans_status"), table_name="scans")
    op.drop_table("scans")

