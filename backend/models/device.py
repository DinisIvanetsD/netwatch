from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class DeviceStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    NEW = "new"
    UNKNOWN = "unknown"


class DeviceSource(StrEnum):
    LIVE = "live"
    DEMO = "demo"


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        Index("ix_devices_source_status", "source", "status"),
        Index("ix_devices_source_ip", "source", "ip_address", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(120))
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    mac_address: Mapped[str | None] = mapped_column(String(17), index=True)
    hostname: Mapped[str | None] = mapped_column(String(255), index=True)
    vendor: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[DeviceStatus] = mapped_column(
        Enum(DeviceStatus, native_enum=False, length=16),
        default=DeviceStatus.UNKNOWN,
        nullable=False,
        index=True,
    )
    source: Mapped[DeviceSource] = mapped_column(
        Enum(DeviceSource, native_enum=False, length=16),
        default=DeviceSource.LIVE,
        nullable=False,
    )
    latency_ms: Mapped[float | None]
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    is_gateway: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    missed_scans: Mapped[int] = mapped_column(default=0, nullable=False)
