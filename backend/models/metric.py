from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class DeviceMetric(Base):
    __tablename__ = "device_metrics"
    __table_args__ = (Index("ix_device_metrics_device_timestamp", "device_id", "timestamp"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    latency_ms: Mapped[float | None] = mapped_column(Float)
    online: Mapped[bool] = mapped_column(Boolean, nullable=False)
