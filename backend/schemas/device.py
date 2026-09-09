from datetime import UTC, datetime
from enum import StrEnum
from ipaddress import ip_address

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.device import DeviceStatus


class DeviceSortField(StrEnum):
    NAME = "name"
    IP_ADDRESS = "ip_address"
    STATUS = "status"
    LATENCY = "latency_ms"
    LAST_SEEN = "last_seen"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None
    ip_address: str
    network_cidr: str
    mac_address: str | None
    hostname: str | None
    vendor: str | None
    status: DeviceStatus
    latency_ms: float | None
    first_seen: datetime
    last_seen: datetime
    created_at: datetime
    updated_at: datetime
    is_gateway: bool
    device_type: str | None
    owner: str | None
    profile_id: int | None
    trust_state: str
    internet_access: str
    lan_access: str
    paused_until: datetime | None
    quarantine_reason: str | None
    quarantined_at: datetime | None
    service_ports: list[int] = Field(default_factory=list)

    @field_validator("ip_address")
    @classmethod
    def validate_ip_address(cls, value: str) -> str:
        return str(ip_address(value))

    @field_validator("first_seen", "last_seen", "created_at", "updated_at", mode="after")
    @classmethod
    def ensure_utc_timezone(cls, value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    @field_validator("paused_until", "quarantined_at", mode="after")
    @classmethod
    def ensure_optional_utc_timezone(cls, value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is not None:
            return value
        return value.replace(tzinfo=UTC)


class DeviceListResponse(BaseModel):
    items: list[DeviceResponse]
    page: int
    per_page: int
    total: int
    pages: int
