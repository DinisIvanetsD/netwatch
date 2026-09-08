"""Add parental-control policy data.

Revision ID: 20260908_0009
Revises: 20260908_0008
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0009"
down_revision: str | None = "20260908_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "control_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(300)),
        sa.Column("internet_enabled", sa.Boolean(), nullable=False),
        sa.Column("safe_search_enabled", sa.Boolean(), nullable=False),
        sa.Column("blocked_categories", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "filter_lists",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("domain_count", sa.Integer(), nullable=False),
        sa.Column("last_updated_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_filter_lists_category", "filter_lists", ["category"])
    op.create_table(
        "domain_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope_type", sa.String(20), nullable=False),
        sa.Column("scope_id", sa.Integer()),
        sa.Column("domain", sa.String(253), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("include_subdomains", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(200)),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_domain_rules_domain", "domain_rules", ["domain"])
    op.create_index("ix_domain_rules_expires_at", "domain_rules", ["expires_at"])
    op.create_index("ix_domain_rules_scope", "domain_rules", ["scope_type", "scope_id", "enabled"])
    op.create_table(
        "access_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.Column("end_minute", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["control_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_access_schedules_profile_day", "access_schedules", ["profile_id", "weekday"])
    with op.batch_alter_table("devices") as batch:
        batch.add_column(sa.Column("device_type", sa.String(40)))
        batch.add_column(sa.Column("owner", sa.String(120)))
        batch.add_column(sa.Column("profile_id", sa.Integer()))
        batch.add_column(sa.Column("trust_state", sa.String(20), server_default="unknown", nullable=False))
        batch.add_column(sa.Column("internet_access", sa.String(20), server_default="allowed", nullable=False))
        batch.add_column(sa.Column("lan_access", sa.String(20), server_default="allowed", nullable=False))
        batch.add_column(sa.Column("paused_until", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("quarantine_reason", sa.String(200)))
        batch.add_column(sa.Column("quarantined_at", sa.DateTime(timezone=True)))
        batch.create_foreign_key("fk_devices_profile_id_control_profiles", "control_profiles", ["profile_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_devices_profile_id", ["profile_id"])
    op.create_table(
        "access_audit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer()),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("result", sa.String(30), nullable=False),
        sa.Column("provider_id", sa.String(40)),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_access_audit_device_id", "access_audit", ["device_id"])


def downgrade() -> None:
    op.drop_table("access_audit")
    with op.batch_alter_table("devices") as batch:
        batch.drop_index("ix_devices_profile_id")
        batch.drop_constraint("fk_devices_profile_id_control_profiles", type_="foreignkey")
        for column in ("quarantined_at", "quarantine_reason", "paused_until", "lan_access", "internet_access", "trust_state", "profile_id", "owner", "device_type"):
            batch.drop_column(column)
    op.drop_table("access_schedules")
    op.drop_table("domain_rules")
    op.drop_table("filter_lists")
    op.drop_table("control_profiles")
