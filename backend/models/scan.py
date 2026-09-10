from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base
from models.device import DeviceSource


class ScanStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, native_enum=False, length=16),
        default=ScanStatus.PENDING,
        nullable=False,
        index=True,
    )
    devices_found: Mapped[int] = mapped_column(default=0, nullable=False)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
    subnet: Mapped[str] = mapped_column(String(45), nullable=False)
    network_id: Mapped[str] = mapped_column(
        String(80), default="legacy", nullable=False, index=True
    )
    source: Mapped[DeviceSource] = mapped_column(
        Enum(DeviceSource, native_enum=False, length=16), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
