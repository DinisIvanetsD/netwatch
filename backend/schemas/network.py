from datetime import datetime

from pydantic import BaseModel


class NetworkStatusResponse(BaseModel):
    subnet: str
    gateway: str | None
    dns_servers: list[str]
    interface_name: str | None = None
    local_ip: str | None = None
    discovery_mode: str = "container"
    auto_detect_network: bool = False
    total_devices: int
    online_devices: int
    average_latency_ms: float | None
    scan_running: bool
    last_completed_scan: datetime | None
    next_scheduled_scan: datetime | None


class ActivityPoint(BaseModel):
    timestamp: datetime
    online_devices: int
    average_latency_ms: float | None
    events: int


class NetworkActivityResponse(BaseModel):
    hours: int
    points: list[ActivityPoint]
