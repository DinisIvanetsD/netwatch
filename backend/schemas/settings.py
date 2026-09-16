from typing import Literal

from pydantic import BaseModel, Field, field_validator

from core.config import normalize_private_subnet

OperatingMode = Literal["simulation", "live"]


class SettingsResponse(BaseModel):
    subnet: str
    auto_detect_network: bool
    scan_interval: int
    scan_concurrency: int
    monitoring_enabled: bool
    service_scan_enabled: bool
    service_ports: list[int]
    offline_after_missed_scans: int
    new_device_alerts: bool
    new_device_policy: Literal["allow", "allow_alert", "quarantine_alert", "block_alert"]
    device_offline_alerts: bool
    new_service_alerts: bool
    latency_alerts: bool
    retention_days: int
    operating_mode: OperatingMode


class SettingsUpdate(BaseModel):
    subnet: str | None = None
    auto_detect_network: bool | None = None
    operating_mode: OperatingMode | None = None
    scan_interval: int | None = Field(default=None, ge=10, le=86_400)
    scan_concurrency: int | None = Field(default=None, ge=1, le=256)
    monitoring_enabled: bool | None = None
    offline_after_missed_scans: int | None = Field(default=None, ge=1, le=20)
    service_scan_enabled: bool | None = None
    service_ports: list[int] | None = Field(default=None, min_length=1, max_length=64)
    new_device_alerts: bool | None = None
    new_device_policy: Literal["allow", "allow_alert", "quarantine_alert", "block_alert"] | None = (
        None
    )
    device_offline_alerts: bool | None = None
    new_service_alerts: bool | None = None
    latency_alerts: bool | None = None
    retention_days: int | None = Field(default=None, ge=1, le=3_650)

    @field_validator("subnet")
    @classmethod
    def validate_subnet(cls, value: str | None) -> str | None:
        return normalize_private_subnet(value) if value is not None else None

    @field_validator("service_ports")
    @classmethod
    def validate_ports(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and any(port < 1 or port > 65535 for port in value):
            raise ValueError("Ports must be between 1 and 65535")
        return list(dict.fromkeys(value)) if value is not None else None


class HistoryClearResponse(BaseModel):
    metrics_deleted: int
    events_deleted: int
    alerts_deleted: int
    scans_deleted: int
    internet_activity_deleted: int
