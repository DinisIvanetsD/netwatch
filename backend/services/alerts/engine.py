from core.config import settings
from models.alert import Alert
from models.device import DeviceSource
from models.event import Event, EventType

TITLES = {
    EventType.DEVICE_DISCOVERED: "New device detected",
    EventType.DEVICE_OFFLINE: "Device offline",
    EventType.SERVICE_DISCOVERED: "New service detected",
    EventType.LATENCY_INCREASED: "Latency increased",
}


def create_alert(event: Event, source: DeviceSource) -> Alert | None:
    if event.type == EventType.DEVICE_DISCOVERED and settings.new_device_policy == "allow":
        return None
    enabled = {
        EventType.DEVICE_DISCOVERED: settings.new_device_alerts,
        EventType.DEVICE_OFFLINE: settings.device_offline_alerts,
        EventType.SERVICE_DISCOVERED: settings.new_service_alerts,
        EventType.LATENCY_INCREASED: settings.latency_alerts,
    }
    if not enabled.get(event.type, False):
        return None
    title = TITLES.get(event.type)
    if title is None:
        return None
    return Alert(
        device_id=event.device_id,
        event_id=event.id,
        type=event.type.value,
        severity=event.severity,
        title=title,
        description=event.message,
        created_at=event.timestamp,
        read=False,
        resolved=False,
        source=source,
    )
