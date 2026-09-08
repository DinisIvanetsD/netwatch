from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.alert import Alert
from models.device import Device, DeviceSource, DeviceStatus
from models.event import Event, EventType
from models.service import Service
from services.alerts.engine import create_alert

AlertKey = tuple[int | None, str, int | None]


def _event_port(event: Event | None) -> int | None:
    if event is None or not isinstance(event.metadata_payload, dict):
        return None
    port = event.metadata_payload.get("port")
    return port if isinstance(port, int) else None


def _alert_key(alert: Alert, event: Event | None) -> AlertKey:
    port = _event_port(event) if alert.type == EventType.SERVICE_DISCOVERED.value else None
    return alert.device_id, alert.type, port


def _event_key(event: Event) -> AlertKey:
    port = _event_port(event) if event.type == EventType.SERVICE_DISCOVERED else None
    return event.device_id, event.type.value, port


def _is_still_active(
    key: AlertKey,
    devices: dict[int, Device],
    services: dict[tuple[int, int], Service],
) -> bool:
    device_id, alert_type, port = key
    device = devices.get(device_id) if device_id is not None else None
    if alert_type == EventType.DEVICE_OFFLINE.value:
        return device is None or device.status == DeviceStatus.OFFLINE
    if alert_type == EventType.LATENCY_INCREASED.value:
        return bool(
            device is None
            or (
                device.status != DeviceStatus.OFFLINE
                and device.latency_ms is not None
                and device.latency_ms >= 75
            )
        )
    if alert_type == EventType.SERVICE_DISCOVERED.value and device_id is not None and port:
        service = services.get((device_id, port))
        return service is None or service.active
    return True


async def reconcile_alerts(
    session: AsyncSession,
    *,
    source: DeviceSource,
    devices: Iterable[Device],
    services: Iterable[Service],
    events: Iterable[Event],
) -> list[Alert]:
    """Resolve stale/duplicate alerts and create only newly active alerts.

    Events remain immutable, so repeated transitions are still available in the
    activity history even when the alert inbox contains only current issues.
    """

    now = datetime.now(UTC)
    devices_by_id = {device.id: device for device in devices if device.id is not None}
    services_by_key = {
        (service.device_id, service.port): service
        for service in services
        if service.device_id is not None
    }
    rows = (
        await session.execute(
            select(Alert, Event)
            .outerjoin(Event, Alert.event_id == Event.id)
            .where(Alert.source == source, Alert.resolved.is_(False))
            .order_by(Alert.created_at.desc(), Alert.id.desc())
        )
    ).all()

    active_by_key: dict[AlertKey, Alert] = {}
    for alert, event in rows:
        key = _alert_key(alert, event)
        if not _is_still_active(key, devices_by_id, services_by_key) or key in active_by_key:
            alert.resolved = True
            alert.resolved_at = now
            continue
        active_by_key[key] = alert

    created: list[Alert] = []
    for event in events:
        alert = create_alert(event, source)
        if alert is None:
            continue
        key = _event_key(event)
        if key in active_by_key:
            continue
        active_by_key[key] = alert
        created.append(alert)
    return created
