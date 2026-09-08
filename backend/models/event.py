from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.device import DeviceSource


class EventSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EventType(StrEnum):
    DEVICE_DISCOVERED = "device.discovered"
    DEVICE_ONLINE = "device.online"
    DEVICE_OFFLINE = "device.offline"
    DEVICE_UPDATED = "device.updated"
    LATENCY_INCREASED = "device.latency_increased"
    SERVICE_DISCOVERED = "service.discovered"
    SERVICE_REMOVED = "service.removed"


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_source_timestamp", "source", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[EventType] = mapped_column(
        Enum(EventType, native_enum=False, length=40), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[EventSeverity] = mapped_column(
        Enum(EventSeverity, native_enum=False, length=16), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    metadata_payload: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    source: Mapped[DeviceSource] = mapped_column(
        Enum(DeviceSource, native_enum=False, length=16), nullable=False
    )
