"""Track verified IP ownership windows for DNS attribution.

Revision ID: 20260910_0014
Revises: 20260910_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0014"
down_revision: str | None = "20260910_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_address_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("network_cidr", sa.String(length=50), nullable=False),
        sa.Column("network_id", sa.String(length=80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_device_address_history")),
    )
    op.create_index(
        "ix_device_address_history_scope_ip_time",
        "device_address_history",
        ["network_cidr", "network_id", "ip_address", "started_at", "ended_at"],
        unique=False,
    )
    op.create_index(
        "ix_device_address_history_device_time",
        "device_address_history",
        ["device_id", "started_at"],
        unique=False,
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO device_address_history
                (device_id, ip_address, network_cidr, network_id, started_at, ended_at)
            SELECT id, ip_address, network_cidr, network_id, first_seen, NULL
            FROM devices
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_address_history_device_time", table_name="device_address_history"
    )
    op.drop_index(
        "ix_device_address_history_scope_ip_time", table_name="device_address_history"
    )
    op.drop_table("device_address_history")
