import hashlib
import logging

from sqlalchemy import select

from database.session import SessionLocal
from models.device import Device, DeviceSource
from models.internet_activity import InternetActivity
from services.activity.classification import classify_domain
from services.providers.dns import DNSCapability, DNSQueryRecord
from services.providers.registry import provider_registry

logger = logging.getLogger(__name__)


async def sync_dns_activity(limit: int = 500) -> int:
    provider = provider_registry.dns
    if not provider.supports(DNSCapability.QUERY_HISTORY):
        return 0
    try:
        records = await provider.query_history(limit=limit)
    except Exception:
        logger.exception("Could not synchronize DNS activity")
        return 0

    async with SessionLocal() as session:
        devices = {
            device.ip_address: device.id
            for device in (
                await session.scalars(select(Device).where(Device.source == DeviceSource.LIVE))
            ).all()
        }
        pending: dict[str, tuple[int, DNSQueryRecord]] = {}
        for record in records:
            device_id = devices.get(record.client)
            if device_id is None:
                continue
            raw_key = "|".join(
                (
                    provider.provider_id,
                    str(device_id),
                    record.timestamp.isoformat(),
                    record.domain,
                    record.query_type or "",
                )
            )
            key = hashlib.sha256(raw_key.encode()).hexdigest()
            pending[key] = (device_id, record)
        keys = list(pending)
        existing = set(
            (
                await session.scalars(
                    select(InternetActivity.record_key).where(InternetActivity.record_key.in_(keys))
                )
            ).all()
        )
        inserted = 0
        for key, value in pending.items():
            if key in existing:
                continue
            device_id, record = value
            session.add(
                InternetActivity(
                    record_key=key,
                    device_id=device_id,
                    provider_id=provider.provider_id,
                    timestamp=record.timestamp,
                    domain=record.domain,
                    category=classify_domain(record.domain),
                    query_type=record.query_type,
                    response_status=record.status,
                    blocked=record.blocked,
                    reason=record.reason,
                )
            )
            inserted += 1
        await session.commit()
        return inserted
