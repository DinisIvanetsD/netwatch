from sqlalchemy import select

from core.config import settings
from database.session import SessionLocal
from models.setting import AppSetting

EDITABLE_KEYS = (
    "netwatch_subnet",
    "auto_detect_network",
    "scan_interval",
    "scan_concurrency",
    "monitoring_enabled",
    "offline_after_missed_scans",
    "service_scan_enabled",
    "service_ports",
    "new_device_alerts",
    "new_device_policy",
    "device_offline_alerts",
    "new_service_alerts",
    "latency_alerts",
    "retention_days",
)
PERSISTED_KEYS = (*EDITABLE_KEYS, "netwatch_network_id")
BOOLEAN_KEYS = {
    "auto_detect_network",
    "service_scan_enabled",
    "monitoring_enabled",
    "new_device_alerts",
    "device_offline_alerts",
    "new_service_alerts",
    "latency_alerts",
}
INTEGER_KEYS = {
    "scan_interval",
    "scan_concurrency",
    "offline_after_missed_scans",
    "retention_days",
}


async def load_persisted_settings() -> None:
    async with SessionLocal() as session:
        records = list(
            (
                await session.scalars(select(AppSetting).where(AppSetting.key.in_(PERSISTED_KEYS)))
            ).all()
        )
    for record in records:
        if record.key == "netwatch_subnet" and isinstance(record.value, str):
            settings.netwatch_subnet = record.value
        elif record.key == "netwatch_network_id" and isinstance(record.value, str):
            settings.netwatch_network_id = record.value
        elif record.key == "service_ports" and isinstance(record.value, list):
            settings.service_ports = ",".join(str(port) for port in record.value)
        elif record.key == "new_device_policy" and isinstance(record.value, str):
            settings.new_device_policy = record.value
        elif (
            record.key in BOOLEAN_KEYS
            and isinstance(record.value, bool)
            or record.key in INTEGER_KEYS
            and isinstance(record.value, int)
        ):
            setattr(settings, record.key, record.value)
