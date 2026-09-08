from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, field_validator


class InternetActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    device_name: str | None = None
    profile_id: int | None
    provider_id: str
    timestamp: datetime
    source_ip: str | None
    destination_ip: str | None
    domain: str
    registered_domain: str | None
    service: str | None
    category: str
    protocol: str | None
    destination_port: int | None
    bytes_sent: int | None
    bytes_received: int | None
    query_type: str | None
    response_status: str
    blocked: bool
    reason: str | None

    @field_validator("timestamp", mode="after")
    @classmethod
    def ensure_utc(cls, value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=UTC)


class InternetActivityListResponse(BaseModel):
    items: list[InternetActivityResponse]
    total: int
    page: int
    per_page: int
    pages: int
    visibility: str = "dns_metadata"


class InternetActivitySummaryResponse(BaseModel):
    total_queries: int
    blocked_queries: int
    active_devices: int
    top_domains: list[dict[str, int | str]]
    top_services: list[dict[str, int | str]]
    categories: list[dict[str, int | str]]
    visibility: str = "dns_metadata"
