"""Add alerts.

Revision ID: 20260908_0006
Revises: 20260908_0005
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0006"
down_revision: str | None = "20260908_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True), sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(40), nullable=False),
        sa.Column("severity", sa.Enum("INFO", "LOW", "MEDIUM", "HIGH", name="eventseverity", native_enum=False, length=16), nullable=False),
        sa.Column("title", sa.String(160), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False), sa.Column("resolved", sa.Boolean(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.Enum("LIVE", "DEMO", name="devicesource", native_enum=False, length=16), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("event_id"))
    for column in ("device_id", "type", "severity", "created_at", "resolved"):
        op.create_index(f"ix_alerts_{column}", "alerts", [column])
    op.create_index("ix_alerts_source_resolved_created", "alerts", ["source", "resolved", "created_at"])


def downgrade() -> None:
    op.drop_table("alerts")
