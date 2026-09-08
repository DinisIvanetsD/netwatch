from pydantic import BaseModel, Field, field_validator


class SettingsResponse(BaseModel):
    subnet: str
    scan_interval: int
    scan_concurrency: int
    monitoring_enabled: bool
    service_scan_enabled: bool
    service_ports: list[int]
    offline_after_missed_scans: int
    new_device_alerts: bool
    device_offline_alerts: bool
    new_service_alerts: bool
    latency_alerts: bool


class SettingsUpdate(BaseModel):
    service_scan_enabled: bool | None = None
    service_ports: list[int] | None = Field(default=None, min_length=1, max_length=64)
    new_device_alerts: bool | None = None
    device_offline_alerts: bool | None = None
    new_service_alerts: bool | None = None
    latency_alerts: bool | None = None

    @field_validator("service_ports")
    @classmethod
    def validate_ports(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and any(port < 1 or port > 65535 for port in value):
            raise ValueError("Ports must be between 1 and 65535")
        return list(dict.fromkeys(value)) if value is not None else None
