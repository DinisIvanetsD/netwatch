from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class InternetActivity(Base):
    __tablename__ = "internet_activity"
    __table_args__ = (
        Index("ix_internet_activity_device_time", "device_id", "timestamp"),
        Index("ix_internet_activity_category_time", "category", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id: Mapped[str] = mapped_column(String(40), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    domain: Mapped[str] = mapped_column(String(253), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    query_type: Mapped[str | None] = mapped_column(String(20))
    response_status: Mapped[str] = mapped_column(String(30), nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(60))
