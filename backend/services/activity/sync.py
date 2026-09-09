import hashlib
import logging

from sqlalchemy import select

from core.config import settings
from database.session import SessionLocal
from models.device import Device, DeviceSource
from models.internet_activity import InternetActivity
from services.activity.classification import domain_classification_service
from services.providers.dns import DNSCapability, DNSQueryRecord
from services.providers.registry import provider_registry
from services.realtime.manager import connection_manager

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
            device.ip_address: device
            for device in (
                await session.scalars(
                    select(Device).where(
                        Device.source == DeviceSource.LIVE,
                        Device.network_cidr == settings.netwatch_subnet,
                    )
                )
            ).all()
        }
        pending: dict[str, tuple[Device, DNSQueryRecord]] = {}
        for record in records:
            device = devices.get(record.client)
            if device is None:
                continue
            raw_key = "|".join(
                (
                    provider.provider_id,
                    str(device.id),
                    record.timestamp.isoformat(),
                    record.domain,
                    record.query_type or "",
                )
            )
            key = hashlib.sha256(raw_key.encode()).hexdigest()
            pending[key] = (device, record)
        keys = list(pending)
        existing = set(
            (
                await session.scalars(
                    select(InternetActivity.record_key).where(InternetActivity.record_key.in_(keys))
                )
            ).all()
        )
        inserted_items: list[InternetActivity] = []
        for key, value in pending.items():
            if key in existing:
                continue
            device, record = value
            classification = domain_classification_service.classify(
                record.domain, block_reason=record.reason
            )
            activity = InternetActivity(
                record_key=key,
                device_id=device.id,
                profile_id=device.profile_id,
                provider_id=provider.provider_id,
                timestamp=record.timestamp,
                source_ip=record.client,
                domain=record.domain,
                registered_domain=classification.registered_domain,
                service=classification.service,
                category=classification.category,
                protocol="dns",
                destination_port=53,
                query_type=record.query_type,
                response_status=record.status,
                blocked=record.blocked,
                reason=record.reason,
            )
            session.add(activity)
            inserted_items.append(activity)
        await session.flush()
        await session.commit()
    if inserted_items:
        await connection_manager.broadcast(
            "internet.activity",
            {"count": len(inserted_items), "provider_id": provider.provider_id},
        )
        for item in [activity for activity in inserted_items if activity.blocked][:25]:
            await connection_manager.broadcast(
                "internet.blocked",
                {
                    "activity_id": item.id,
                    "device_id": item.device_id,
                    "domain": item.domain,
                    "category": item.category,
                },
            )
    return len(inserted_items)
