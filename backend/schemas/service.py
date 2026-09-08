from datetime import UTC, datetime

from pydantic import BaseModel, field_validator


class ServiceResponse(BaseModel):
    id: int
    device_id: int
    device_name: str
    ip_address: str
    port: int
    protocol: str
    service_name: str
    first_seen: datetime
    last_seen: datetime
    active: bool

    @field_validator("first_seen", "last_seen", mode="after")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class ServiceListResponse(BaseModel):
    items: list[ServiceResponse]
    total: int
