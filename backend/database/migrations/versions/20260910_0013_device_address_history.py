"""Allow historical IP reuse and persist control identifiers.

Revision ID: 20260910_0013
Revises: 20260909_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260910_0013"
down_revision: str | None = "20260909_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("devices") as batch:
        batch.drop_index("ix_devices_source_network_ip")
        batch.drop_index("ix_devices_source_network_status")
        batch.add_column(
            sa.Column("network_id", sa.String(length=80), nullable=False, server_default="legacy")
        )
        batch.create_index(
            "ix_devices_source_network_ip",
            ["source", "network_cidr", "network_id", "ip_address"],
            unique=False,
        )
        batch.create_index(
            "ix_devices_source_network_status",
            ["source", "network_cidr", "network_id", "status"],
            unique=False,
        )
        batch.add_column(sa.Column("control_provider_id", sa.String(length=40)))
        batch.add_column(sa.Column("control_identifier", sa.String(length=100)))
    with op.batch_alter_table("scans") as batch:
        batch.add_column(
            sa.Column("network_id", sa.String(length=80), nullable=False, server_default="legacy")
        )
        batch.create_index("ix_scans_network_id", ["network_id"], unique=False)


def downgrade() -> None:
    connection = op.get_bind()
    duplicate = connection.execute(
        sa.text(
            """
            SELECT source, network_cidr, ip_address
            FROM devices
            GROUP BY source, network_cidr, ip_address
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Cannot restore the unique device-IP index while historical IP reuse exists."
        )
    with op.batch_alter_table("scans") as batch:
        batch.drop_index("ix_scans_network_id")
        batch.drop_column("network_id")
    with op.batch_alter_table("devices") as batch:
        batch.drop_column("control_identifier")
        batch.drop_column("control_provider_id")
        batch.drop_index("ix_devices_source_network_status")
        batch.drop_index("ix_devices_source_network_ip")
        batch.drop_column("network_id")
        batch.create_index(
            "ix_devices_source_network_ip",
            ["source", "network_cidr", "ip_address"],
            unique=True,
        )
        batch.create_index(
            "ix_devices_source_network_status",
            ["source", "network_cidr", "status"],
            unique=False,
        )
