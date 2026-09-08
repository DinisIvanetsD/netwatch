"""Add DNS-derived internet activity.

Revision ID: 20260908_0008
Revises: 20260908_0007
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0008"
down_revision: str | None = "20260908_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "internet_activity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("record_key", sa.String(64), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.String(40), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("domain", sa.String(253), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("query_type", sa.String(20), nullable=True),
        sa.Column("response_status", sa.String(30), nullable=False),
        sa.Column("blocked", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(60), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("record_key"),
    )
    for column in ("device_id", "domain", "blocked"):
        op.create_index(f"ix_internet_activity_{column}", "internet_activity", [column])
    op.create_index(
        "ix_internet_activity_device_time", "internet_activity", ["device_id", "timestamp"]
    )
    op.create_index(
        "ix_internet_activity_category_time", "internet_activity", ["category", "timestamp"]
    )


def downgrade() -> None:
    op.drop_table("internet_activity")
