from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class InternetActivity(Base):
    __tablename__ = "internet_activity"
    __table_args__ = (
        Index("ix_internet_activity_device_time", "device_id", "timestamp"),
        Index("ix_internet_activity_category_time", "category", "timestamp"),
        Index("ix_internet_activity_profile_time", "profile_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    record_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id: Mapped[str] = mapped_column(String(40), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_ip: Mapped[str | None] = mapped_column(String(45))
    destination_ip: Mapped[str | None] = mapped_column(String(45))
    domain: Mapped[str] = mapped_column(String(253), nullable=False, index=True)
    registered_domain: Mapped[str | None] = mapped_column(String(253), index=True)
    service: Mapped[str | None] = mapped_column(String(80), index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    protocol: Mapped[str | None] = mapped_column(String(20))
    destination_port: Mapped[int | None] = mapped_column(Integer)
    bytes_sent: Mapped[int | None] = mapped_column(BigInteger)
    bytes_received: Mapped[int | None] = mapped_column(BigInteger)
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("control_profiles.id", ondelete="SET NULL"), index=True
    )
    query_type: Mapped[str | None] = mapped_column(String(20))
    response_status: Mapped[str] = mapped_column(String(30), nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(60))
