from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.device import DeviceSource
from models.event import EventSeverity


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_source_resolved_created", "source", "resolved", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), unique=True
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    severity: Mapped[EventSeverity] = mapped_column(
        Enum(EventSeverity, native_enum=False, length=16), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[DeviceSource] = mapped_column(
        Enum(DeviceSource, native_enum=False, length=16), nullable=False
    )
