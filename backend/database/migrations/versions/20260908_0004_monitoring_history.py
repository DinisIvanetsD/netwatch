"""Add monitoring history and event tables.

Revision ID: 20260908_0004
Revises: 20260908_0003
Create Date: 2026-09-08 01:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0004"
down_revision: str | None = "20260908_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "devices",
        sa.Column("missed_scans", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "device_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("online", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], name=op.f("fk_device_metrics_device_id_devices"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_device_metrics")),
    )
    op.create_index(op.f("ix_device_metrics_device_id"), "device_metrics", ["device_id"])
    op.create_index(op.f("ix_device_metrics_timestamp"), "device_metrics", ["timestamp"])
    op.create_index("ix_device_metrics_device_timestamp", "device_metrics", ["device_id", "timestamp"])
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.Enum("DEVICE_DISCOVERED", "DEVICE_ONLINE", "DEVICE_OFFLINE", "DEVICE_UPDATED", "LATENCY_INCREASED", "SERVICE_DISCOVERED", "SERVICE_REMOVED", name="eventtype", native_enum=False, length=40), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.Enum("INFO", "LOW", "MEDIUM", "HIGH", name="eventseverity", native_enum=False, length=16), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("source", sa.Enum("LIVE", "DEMO", name="devicesource", native_enum=False, length=16), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], name=op.f("fk_events_device_id_devices"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    op.create_index(op.f("ix_events_device_id"), "events", ["device_id"])
    op.create_index(op.f("ix_events_severity"), "events", ["severity"])
    op.create_index(op.f("ix_events_timestamp"), "events", ["timestamp"])
    op.create_index(op.f("ix_events_type"), "events", ["type"])
    op.create_index("ix_events_source_timestamp", "events", ["source", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_events_source_timestamp", table_name="events")
    op.drop_index(op.f("ix_events_type"), table_name="events")
    op.drop_index(op.f("ix_events_timestamp"), table_name="events")
    op.drop_index(op.f("ix_events_severity"), table_name="events")
    op.drop_index(op.f("ix_events_device_id"), table_name="events")
    op.drop_table("events")
    op.drop_index("ix_device_metrics_device_timestamp", table_name="device_metrics")
    op.drop_index(op.f("ix_device_metrics_timestamp"), table_name="device_metrics")
    op.drop_index(op.f("ix_device_metrics_device_id"), table_name="device_metrics")
    op.drop_table("device_metrics")
    op.drop_column("devices", "missed_scans")
