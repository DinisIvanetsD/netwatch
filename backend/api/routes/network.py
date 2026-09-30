from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.devices import active_source
from core.config import settings
from database.session import get_session
from models.device import Device, DeviceStatus
from models.event import Event
from models.metric import DeviceMetric
from models.scan import Scan, ScanStatus
from schemas.network import (
    ActivityPoint,
    NetworkActivityResponse,
    NetworkHistoryItem,
    NetworkHistoryResponse,
    NetworkProfileListResponse,
    NetworkProfileResponse,
    NetworkStatusResponse,
)
from services.scanner.coordinator import scan_coordinator
from services.scanner.service import scan_service

router = APIRouter(prefix="/network", tags=["network"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("/profiles", response_model=NetworkProfileListResponse)
async def network_profiles(session: SessionDependency) -> NetworkProfileListResponse:
    """Return network contexts observed by NetWatch without mixing inventories."""

    source = active_source()
    scan_groups = list(
        (
            await session.execute(
                select(
                    Scan.subnet,
                    Scan.network_id,
                    func.count(Scan.id).label("scan_count"),
                    func.max(func.coalesce(Scan.finished_at, Scan.created_at)).label("last_seen"),
                )
                .where(Scan.source == source)
                .group_by(Scan.subnet, Scan.network_id)
            )
        ).all()
    )
    device_groups = {
        (subnet, network_id): int(count)
        for subnet, network_id, count in (
            await session.execute(
                select(
                    Device.network_cidr,
                    Device.network_id,
                    func.count(Device.id),
                )
                .where(Device.source == source)
                .group_by(Device.network_cidr, Device.network_id)
            )
        ).all()
    }

    current_key = (settings.netwatch_subnet, settings.netwatch_network_id)
    observed_keys = {(subnet, network_id) for subnet, network_id, *_ in scan_groups}
    observed_keys.update(device_groups)
    observed_keys.add(current_key)
    scan_by_key = {
        (subnet, network_id): (int(scan_count), last_seen)
        for subnet, network_id, scan_count, last_seen in scan_groups
    }

    items: list[NetworkProfileResponse] = []
    for subnet, network_id in observed_keys:
        scan_count, last_seen = scan_by_key.get((subnet, network_id), (0, None))
        is_current = (subnet, network_id) == current_key
        items.append(
            NetworkProfileResponse(
                subnet=subnet,
                network_id=network_id,
                label="Current network" if is_current else "Previously observed network",
                is_current=is_current,
                devices_known=device_groups.get((subnet, network_id), 0),
                scan_count=scan_count,
                last_seen=last_seen,
            )
        )

    items.sort(
        key=lambda item: (
            not item.is_current,
            -(item.last_seen.timestamp() if item.last_seen else 0),
            item.subnet,
            item.network_id,
        )
    )
    return NetworkProfileListResponse(items=items)


@dataclass
class ActivityBucket:
    online_devices: set[int] = field(default_factory=set)
    latencies: list[float] = field(default_factory=list)
    events: int = 0


@router.get("/status", response_model=NetworkStatusResponse)
async def network_status(session: SessionDependency) -> NetworkStatusResponse:
    source = active_source()
    devices = list(
        (
            await session.scalars(
                select(Device).where(
                    Device.source == source,
                    Device.network_cidr == settings.netwatch_subnet,
                    Device.network_id == settings.netwatch_network_id,
                )
            )
        ).all()
    )
    online = [
        device for device in devices if device.status in {DeviceStatus.ONLINE, DeviceStatus.NEW}
    ]
    latencies = [device.latency_ms for device in online if device.latency_ms is not None]
    environment = scan_service.last_environment
    if environment is not None and (
        environment.subnet != settings.netwatch_subnet
        or environment.network_id != settings.netwatch_network_id
    ):
        environment = None
    gateway = next((device.ip_address for device in devices if device.is_gateway), None)
    last_scan = await session.scalar(
        select(Scan)
        .where(
            Scan.source == source,
            Scan.subnet == settings.netwatch_subnet,
            Scan.network_id == settings.netwatch_network_id,
            Scan.status == ScanStatus.COMPLETED,
        )
        .order_by(Scan.finished_at.desc(), Scan.id.desc())
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
        network_id=settings.netwatch_network_id,
        gateway=gateway or (environment.gateway if environment else None),
        dns_servers=list(environment.dns_servers) if environment else [],
        interface_name=environment.interface_name if environment else None,
        local_ip=environment.local_ip if environment else None,
        discovery_mode="windows_sensor" if environment else "container",
        auto_detect_network=settings.auto_detect_network,
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
            .where(
                Device.source == active_source(),
                Device.network_cidr == settings.netwatch_subnet,
                Device.network_id == settings.netwatch_network_id,
                DeviceMetric.timestamp >= since,
            )
            .order_by(DeviceMetric.timestamp, DeviceMetric.id)
        )
    ).all()
    event_rows = list(
        (
            await session.scalars(
                select(Event)
                .join(Device, Device.id == Event.device_id)
                .where(
                    Event.source == active_source(),
                    Device.network_cidr == settings.netwatch_subnet,
                    Device.network_id == settings.netwatch_network_id,
                    Event.timestamp >= since,
                )
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


@router.get("/history", response_model=NetworkHistoryResponse)
async def network_history(
    session: SessionDependency,
    hours: Annotated[int, Query(ge=1, le=168)] = 168,
) -> NetworkHistoryResponse:
    """Return per-device metric summaries for the current network in one query."""

    since = datetime.now(UTC) - timedelta(hours=hours)
    rows = (
        await session.execute(
            select(
                Device.id,
                func.count(DeviceMetric.id),
                func.sum(case((DeviceMetric.online.is_(True), 1), else_=0)),
                func.avg(DeviceMetric.latency_ms),
                func.max(DeviceMetric.timestamp),
            )
            .join(DeviceMetric, DeviceMetric.device_id == Device.id)
            .where(
                Device.source == active_source(),
                Device.network_cidr == settings.netwatch_subnet,
                Device.network_id == settings.netwatch_network_id,
                DeviceMetric.timestamp >= since,
            )
            .group_by(Device.id)
            .order_by(Device.id),
        )
    ).all()
    return NetworkHistoryResponse(
        hours=hours,
        items=[
            NetworkHistoryItem(
                device_id=device_id,
                sample_count=int(sample_count),
                online_samples=int(online_samples or 0),
                average_latency_ms=(
                    float(average_latency) if average_latency is not None else None
                ),
                last_sample_at=last_sample_at,
            )
            for device_id, sample_count, online_samples, average_latency, last_sample_at in rows
        ],
    )
