from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from models.scan import ScanStatus


class ScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime | None
    finished_at: datetime | None
    status: ScanStatus
    devices_found: int
    duration_ms: float | None
    error: str | None
    subnet: str
    created_at: datetime

    @field_validator("started_at", "finished_at", "created_at", mode="after")
    @classmethod
    def ensure_utc_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)


class ScanListResponse(BaseModel):
    items: list[ScanResponse]
    page: int
    per_page: int
    total: int
    pages: int
