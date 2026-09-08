from datetime import datetime

from pydantic import BaseModel


class NetworkStatusResponse(BaseModel):
    subnet: str
    gateway: str | None
    dns_servers: list[str]
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
