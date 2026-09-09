"""Scope device inventory to the monitored network.

Revision ID: 20260909_0012
Revises: 20260909_0011
"""

import json
from collections.abc import Sequence
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network

import sqlalchemy as sa
from alembic import op

revision: str = "20260909_0012"
down_revision: str | None = "20260909_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _configured_subnet() -> str:
    connection = op.get_bind()
    value = connection.execute(
        sa.text("SELECT value FROM app_settings WHERE key = 'netwatch_subnet'")
    ).scalar_one_or_none()
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            decoded = value
        if isinstance(decoded, str) and decoded:
            return decoded
    return "192.168.1.0/24"


def _known_networks() -> list[IPv4Network]:
    connection = op.get_bind()
    values = [
        row[0]
        for row in connection.execute(
            sa.text(
                """
                SELECT subnet
                FROM scans
                GROUP BY subnet
                ORDER BY MAX(created_at) DESC
                """
            )
        )
    ]
    values.append(_configured_subnet())
    networks: list[IPv4Network] = []
    for value in values:
        try:
            network = ip_network(value)
        except ValueError:
            continue
        if isinstance(network, IPv4Network) and network not in networks:
            networks.append(network)
    return networks


def _scope_for_address(address: str, networks: list[IPv4Network], fallback: str) -> str:
    try:
        parsed = ip_address(address)
    except ValueError:
        return fallback
    if not isinstance(parsed, IPv4Address):
        return fallback
    matches = [network for network in networks if parsed in network]
    return str(max(matches, key=lambda network: network.prefixlen)) if matches else fallback


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE devices SET profile_id = NULL "
            "WHERE profile_id IS NOT NULL "
            "AND profile_id NOT IN (SELECT id FROM control_profiles)"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE internet_activity SET profile_id = NULL "
            "WHERE profile_id IS NOT NULL "
            "AND profile_id NOT IN (SELECT id FROM control_profiles)"
        )
    )
    connection.execute(
        sa.text(
            "DELETE FROM access_schedules "
            "WHERE profile_id NOT IN (SELECT id FROM control_profiles)"
        )
    )
    with op.batch_alter_table("devices") as batch:
        batch.drop_index("ix_devices_source_ip")
        batch.add_column(sa.Column("network_cidr", sa.String(length=50), nullable=True))

    fallback = _configured_subnet()
    networks = _known_networks()
    rows = connection.execute(sa.text("SELECT id, ip_address FROM devices")).all()
    for device_id, address in rows:
        connection.execute(
            sa.text("UPDATE devices SET network_cidr = :network_cidr WHERE id = :device_id"),
            {
                "network_cidr": _scope_for_address(address, networks, fallback),
                "device_id": device_id,
            },
        )

    with op.batch_alter_table("devices") as batch:
        batch.alter_column("network_cidr", existing_type=sa.String(length=50), nullable=False)
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


def downgrade() -> None:
    connection = op.get_bind()
    duplicate_ids = list(
        connection.execute(
            sa.text(
                """
                SELECT duplicate.id
                FROM devices AS duplicate
                JOIN devices AS keeper
                  ON keeper.source = duplicate.source
                 AND keeper.ip_address = duplicate.ip_address
                 AND keeper.id < duplicate.id
                """
            )
        ).scalars()
    )
    if duplicate_ids:
        statement = sa.text("DELETE FROM devices WHERE id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        )
        connection.execute(statement, {"ids": duplicate_ids})

    with op.batch_alter_table("devices") as batch:
        batch.drop_index("ix_devices_source_network_status")
        batch.drop_index("ix_devices_source_network_ip")
        batch.drop_column("network_cidr")
        batch.create_index("ix_devices_source_ip", ["source", "ip_address"], unique=True)
