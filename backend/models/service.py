from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("device_id", "port", "protocol", name="uq_services_device_port_protocol"),
        Index("ix_services_active_name", "active", "service_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    port: Mapped[int] = mapped_column(nullable=False, index=True)
    protocol: Mapped[str] = mapped_column(String(8), default="tcp", nullable=False)
    service_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
