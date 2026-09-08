from sqlalchemy import select

from core.config import settings
from database.session import SessionLocal
from models.setting import AppSetting

EDITABLE_KEYS = (
    "service_scan_enabled",
    "service_ports",
    "new_device_alerts",
    "device_offline_alerts",
    "new_service_alerts",
    "latency_alerts",
)


async def load_persisted_settings() -> None:
    async with SessionLocal() as session:
        records = list(
            (
                await session.scalars(select(AppSetting).where(AppSetting.key.in_(EDITABLE_KEYS)))
            ).all()
        )
    for record in records:
        if record.key == "service_scan_enabled" and isinstance(record.value, bool):
            settings.service_scan_enabled = record.value
        elif record.key == "service_ports" and isinstance(record.value, list):
            settings.service_ports = ",".join(str(port) for port in record.value)
        elif record.key in EDITABLE_KEYS and isinstance(record.value, bool):
            setattr(settings, record.key, record.value)
