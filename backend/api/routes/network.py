from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.devices import active_source
from core.config import settings
from database.session import get_session
from models.device import Device, DeviceStatus
from models.event import Event
from models.metric import DeviceMetric
from models.scan import Scan, ScanStatus
from schemas.network import ActivityPoint, NetworkActivityResponse, NetworkStatusResponse
from services.scanner.coordinator import scan_coordinator

router = APIRouter(prefix="/network", tags=["network"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@dataclass
class ActivityBucket:
    online_devices: set[int] = field(default_factory=set)
    latencies: list[float] = field(default_factory=list)
    events: int = 0


@router.get("/status", response_model=NetworkStatusResponse)
async def network_status(session: SessionDependency) -> NetworkStatusResponse:
    source = active_source()
    devices = list((await session.scalars(select(Device).where(Device.source == source))).all())
    online = [
        device for device in devices if device.status in {DeviceStatus.ONLINE, DeviceStatus.NEW}
    ]
    latencies = [device.latency_ms for device in online if device.latency_ms is not None]
    gateway = next((device.ip_address for device in devices if device.is_gateway), None)
    last_scan = await session.scalar(
        select(Scan)
        .where(Scan.source == source, Scan.status == ScanStatus.COMPLETED)
        .order_by(Scan.finished_at.desc())
        .limit(1)
    )
    last_completed = last_scan.finished_at if last_scan else None
    next_scan = (
        last_completed + timedelta(seconds=settings.scan_interval)
        if last_completed and settings.monitoring_enabled
        else None
    )
    return NetworkStatusResponse(
        subnet=settings.netwatch_subnet,
        gateway=gateway,
        dns_servers=[],
        total_devices=len(devices),
        online_devices=len(online),
        average_latency_ms=sum(latencies) / len(latencies) if latencies else None,
        scan_running=scan_coordinator.running,
        last_completed_scan=last_completed,
        next_scheduled_scan=next_scan,
    )


@router.get("/activity", response_model=NetworkActivityResponse)
async def network_activity(
    session: SessionDependency,
    hours: Annotated[int, Query(ge=1, le=168)] = 24,
) -> NetworkActivityResponse:
    since = datetime.now(UTC) - timedelta(hours=hours)
    metric_rows = (
        await session.execute(
            select(DeviceMetric, Device.id)
            .join(Device)
            .where(Device.source == active_source(), DeviceMetric.timestamp >= since)
            .order_by(DeviceMetric.timestamp)
        )
    ).all()
    event_rows = list(
        (
            await session.scalars(
                select(Event).where(Event.source == active_source(), Event.timestamp >= since)
            )
        ).all()
    )
    buckets: defaultdict[datetime, ActivityBucket] = defaultdict(ActivityBucket)
    for metric, device_id in metric_rows:
        stamp = metric.timestamp.replace(minute=0, second=0, microsecond=0)
        if metric.online:
            buckets[stamp].online_devices.add(device_id)
        if metric.latency_ms is not None:
            buckets[stamp].latencies.append(metric.latency_ms)
    for event in event_rows:
        stamp = event.timestamp.replace(minute=0, second=0, microsecond=0)
        buckets[stamp].events += 1
    points = []
    for stamp in sorted(buckets):
        values = buckets[stamp]
        points.append(
            ActivityPoint(
                timestamp=stamp,
                online_devices=len(values.online_devices),
                average_latency_ms=(
                    sum(values.latencies) / len(values.latencies) if values.latencies else None
                ),
                events=values.events,
            )
        )
    return NetworkActivityResponse(hours=hours, points=points)
