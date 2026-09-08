from datetime import UTC, datetime

from pydantic import BaseModel, field_validator

from models.event import EventSeverity


class AlertResponse(BaseModel):
    id: int
    device_id: int | None
    device_name: str | None
    type: str
    severity: EventSeverity
    title: str
    description: str
    created_at: datetime
    read: bool
    resolved: bool
    resolved_at: datetime | None

    @field_validator("created_at", "resolved_at", mode="after")
    @classmethod
    def ensure_utc(cls, value: datetime | None) -> datetime | None:
        return value if value is None or value.tzinfo is not None else value.replace(tzinfo=UTC)


class AlertListResponse(BaseModel):
    items: list[AlertResponse]
    total: int


class AlertUpdate(BaseModel):
    read: bool | None = None
    resolved: bool | None = None
