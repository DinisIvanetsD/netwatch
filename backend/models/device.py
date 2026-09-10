from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, func
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
        Index(
            "ix_devices_source_network_ip",
            "source",
            "network_cidr",
            "network_id",
            "ip_address",
            unique=False,
        ),
        Index(
            "ix_devices_source_network_status",
            "source",
            "network_cidr",
            "network_id",
            "status",
        ),
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
    network_cidr: Mapped[str] = mapped_column(String(50), nullable=False)
    network_id: Mapped[str] = mapped_column(String(80), default="legacy", nullable=False)
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
    device_type: Mapped[str | None] = mapped_column(String(40))
    owner: Mapped[str | None] = mapped_column(String(120))
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("control_profiles.id", ondelete="SET NULL"), index=True
    )
    trust_state: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    internet_access: Mapped[str] = mapped_column(String(20), default="allowed", nullable=False)
    lan_access: Mapped[str] = mapped_column(String(20), default="allowed", nullable=False)
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quarantine_reason: Mapped[str | None] = mapped_column(String(200))
    quarantined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    control_provider_id: Mapped[str | None] = mapped_column(String(40))
    control_identifier: Mapped[str | None] = mapped_column(String(100))
