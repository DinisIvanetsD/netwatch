"""Create devices table.

Revision ID: 20260908_0002
Revises: 20260908_0001
Create Date: 2026-09-08 00:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0002"
down_revision: str | None = "20260908_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("mac_address", sa.String(length=17), nullable=True),
        sa.Column("hostname", sa.String(length=255), nullable=True),
        sa.Column("vendor", sa.String(length=255), nullable=True),
        sa.Column("status", sa.Enum("ONLINE", "OFFLINE", "NEW", "UNKNOWN", name="devicestatus", native_enum=False, length=16), nullable=False),
        sa.Column("source", sa.Enum("LIVE", "DEMO", name="devicesource", native_enum=False, length=16), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("is_gateway", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
    )
    op.create_index(op.f("ix_devices_hostname"), "devices", ["hostname"], unique=False)
    op.create_index(op.f("ix_devices_ip_address"), "devices", ["ip_address"], unique=False)
    op.create_index(op.f("ix_devices_mac_address"), "devices", ["mac_address"], unique=False)
    op.create_index("ix_devices_source_ip", "devices", ["source", "ip_address"], unique=True)
    op.create_index("ix_devices_source_status", "devices", ["source", "status"], unique=False)
    op.create_index(op.f("ix_devices_status"), "devices", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_devices_status"), table_name="devices")
    op.drop_index("ix_devices_source_status", table_name="devices")
    op.drop_index("ix_devices_source_ip", table_name="devices")
    op.drop_index(op.f("ix_devices_mac_address"), table_name="devices")
    op.drop_index(op.f("ix_devices_ip_address"), table_name="devices")
    op.drop_index(op.f("ix_devices_hostname"), table_name="devices")
    op.drop_table("devices")

