from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class DeviceAddressHistory(Base):
    """Verified ownership windows for a device address on a physical LAN."""

    __tablename__ = "device_address_history"
    __table_args__ = (
        Index(
            "ix_device_address_history_scope_ip_time",
            "network_cidr",
            "network_id",
            "ip_address",
            "started_at",
            "ended_at",
        ),
        Index("ix_device_address_history_device_time", "device_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    network_cidr: Mapped[str] = mapped_column(String(50), nullable=False)
    network_id: Mapped[str] = mapped_column(String(80), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
