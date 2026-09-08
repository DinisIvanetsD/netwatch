"""Add control enforcement state and richer DNS observations.

Revision ID: 20260908_0010
Revises: 20260908_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0010"
down_revision: str | None = "20260908_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    device_source = sa.Enum("LIVE", "DEMO", name="devicesource", native_enum=False, length=16)
    with op.batch_alter_table("control_profiles") as batch:
        batch.add_column(sa.Column("source", device_source, server_default="LIVE", nullable=False))
        batch.drop_constraint("uq_control_profiles_name", type_="unique")
        batch.create_index("ix_control_profiles_source_name", ["source", "name"], unique=True)

    with op.batch_alter_table("domain_rules") as batch:
        batch.add_column(sa.Column("source", device_source, server_default="LIVE", nullable=False))
        batch.add_column(sa.Column("provider_reference", sa.String(40)))
        batch.add_column(sa.Column("provider_rule", sa.String(600)))
        batch.add_column(
            sa.Column(
                "enforcement_status",
                sa.String(20),
                server_default="pending",
                nullable=False,
            )
        )
        batch.add_column(sa.Column("enforcement_error", sa.String(300)))
        batch.add_column(sa.Column("last_applied_at", sa.DateTime(timezone=True)))
        batch.create_unique_constraint("uq_domain_rules_provider_reference", ["provider_reference"])
        batch.create_index("ix_domain_rules_enforcement_status", ["enforcement_status"])
        batch.create_index("ix_domain_rules_source", ["source"])

    with op.batch_alter_table("filter_lists") as batch:
        batch.add_column(sa.Column("source", device_source, server_default="LIVE", nullable=False))
        batch.create_index("ix_filter_lists_source", ["source"])

    with op.batch_alter_table("access_audit") as batch:
        batch.add_column(sa.Column("source", device_source, server_default="LIVE", nullable=False))
        batch.add_column(
            sa.Column(
                "actor",
                sa.String(20),
                server_default="administrator",
                nullable=False,
            )
        )
        batch.create_index("ix_access_audit_source", ["source"])

    with op.batch_alter_table("internet_activity") as batch:
        batch.add_column(sa.Column("source_ip", sa.String(45)))
        batch.add_column(sa.Column("destination_ip", sa.String(45)))
        batch.add_column(sa.Column("registered_domain", sa.String(253)))
        batch.add_column(sa.Column("service", sa.String(80)))
        batch.add_column(sa.Column("protocol", sa.String(20)))
        batch.add_column(sa.Column("destination_port", sa.Integer()))
        batch.add_column(sa.Column("bytes_sent", sa.BigInteger()))
        batch.add_column(sa.Column("bytes_received", sa.BigInteger()))
        batch.add_column(sa.Column("profile_id", sa.Integer()))
        batch.create_foreign_key(
            "fk_internet_activity_profile_id_control_profiles",
            "control_profiles",
            ["profile_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_internet_activity_registered_domain", ["registered_domain"])
        batch.create_index("ix_internet_activity_service", ["service"])
        batch.create_index("ix_internet_activity_profile_id", ["profile_id"])
        batch.create_index("ix_internet_activity_profile_time", ["profile_id", "timestamp"])


def downgrade() -> None:
    with op.batch_alter_table("internet_activity") as batch:
        batch.drop_index("ix_internet_activity_profile_time")
        batch.drop_index("ix_internet_activity_profile_id")
        batch.drop_index("ix_internet_activity_service")
        batch.drop_index("ix_internet_activity_registered_domain")
        batch.drop_constraint(
            "fk_internet_activity_profile_id_control_profiles", type_="foreignkey"
        )
        for column in (
            "profile_id",
            "bytes_received",
            "bytes_sent",
            "destination_port",
            "protocol",
            "service",
            "registered_domain",
            "destination_ip",
            "source_ip",
        ):
            batch.drop_column(column)

    with op.batch_alter_table("access_audit") as batch:
        batch.drop_index("ix_access_audit_source")
        batch.drop_column("source")
        batch.drop_column("actor")

    with op.batch_alter_table("filter_lists") as batch:
        batch.drop_index("ix_filter_lists_source")
        batch.drop_column("source")

    with op.batch_alter_table("domain_rules") as batch:
        batch.drop_index("ix_domain_rules_source")
        batch.drop_index("ix_domain_rules_enforcement_status")
        batch.drop_constraint("uq_domain_rules_provider_reference", type_="unique")
        for column in (
            "last_applied_at",
            "enforcement_error",
            "enforcement_status",
            "provider_rule",
            "provider_reference",
            "source",
        ):
            batch.drop_column(column)

    with op.batch_alter_table("control_profiles") as batch:
        batch.drop_index("ix_control_profiles_source_name")
        batch.drop_column("source")
        batch.create_unique_constraint("uq_control_profiles_name", ["name"])
