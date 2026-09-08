"""Add detected services.

Revision ID: 20260908_0005
Revises: 20260908_0004
"""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20260908_0005"
down_revision: str | None = "20260908_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.String(length=8), nullable=False),
        sa.Column("service_name", sa.String(length=64), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "port", "protocol", name="uq_services_device_port_protocol"),
    )
    for column in ("device_id", "port", "service_name", "active"):
        op.create_index(f"ix_services_{column}", "services", [column])
    op.create_index("ix_services_active_name", "services", ["active", "service_name"])


def downgrade() -> None:
    op.drop_table("services")
