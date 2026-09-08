from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from models.event import EventSeverity, EventType


class MetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    timestamp: datetime
    latency_ms: float | None
    online: bool

    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class MetricListResponse(BaseModel):
    items: list[MetricResponse]
    page: int
    per_page: int
    total: int
    pages: int


class EventResponse(BaseModel):
    id: int
    device_id: int | None
    device_name: str | None
    type: EventType
    message: str
    severity: EventSeverity
    timestamp: datetime
    metadata: dict[str, object]

    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class EventListResponse(BaseModel):
    items: list[EventResponse]
    page: int
    per_page: int
    total: int
    pages: int
