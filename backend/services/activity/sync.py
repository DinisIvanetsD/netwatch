import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from core.config import settings
from database.session import SessionLocal
from models.device import Device, DeviceSource
from models.device_address import DeviceAddressHistory
from models.internet_activity import InternetActivity
from services.activity.classification import domain_classification_service
from services.providers.dns import DNSCapability, DNSQueryRecord
from services.providers.registry import provider_registry
from services.realtime.manager import connection_manager

logger = logging.getLogger(__name__)


def _utc(value: datetime) -> datetime:
    """Normalize database-loaded and provider timestamps for interval comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def resolve_record_owners(
    record: DNSQueryRecord,
    histories_by_ip: dict[str, list[DeviceAddressHistory]],
    device_by_id: dict[int, Device],
) -> list[Device]:
    timestamp = _utc(record.timestamp)
    owners_by_id: dict[int, Device] = {}
    for history in histories_by_ip.get(record.client, []):
        started_at = _utc(history.started_at)
        ended_at = _utc(history.ended_at) if history.ended_at else None
        if started_at <= timestamp and (ended_at is None or timestamp <= ended_at):
            device = device_by_id.get(history.device_id)
            if device is not None and device.id is not None:
                owners_by_id[device.id] = device
    return list(owners_by_id.values())


async def sync_dns_activity(limit: int = 500) -> int:
    provider = provider_registry.dns
    if not provider.supports(DNSCapability.QUERY_HISTORY):
        return 0
    try:
        records = await provider.query_history(limit=limit)
    except Exception as error:
        # Provider outages are expected while DNS is being configured. Keep the
        # monitoring loop healthy without flooding logs with a traceback every
        # interval; the diagnostics endpoint exposes the actionable reason.
        logger.warning("DNS activity sync skipped: %s", error)
        return 0

    async with SessionLocal() as session:
        devices = list(
            (
                await session.scalars(
                    select(Device).where(
                        Device.source == DeviceSource.LIVE,
                        Device.network_cidr == settings.netwatch_subnet,
                        Device.network_id == settings.netwatch_network_id,
                    )
                )
            ).all()
        )
        device_by_id = {device.id: device for device in devices}
        histories = list(
            (
                await session.scalars(
                    select(DeviceAddressHistory).where(
                        DeviceAddressHistory.device_id.in_(device_by_id),
                        DeviceAddressHistory.network_cidr == settings.netwatch_subnet,
                        DeviceAddressHistory.network_id == settings.netwatch_network_id,
                    )
                )
            ).all()
        )
        histories_by_ip: dict[str, list[DeviceAddressHistory]] = {}
        for history in histories:
            histories_by_ip.setdefault(history.ip_address, []).append(history)

        pending: dict[str, tuple[Device, DNSQueryRecord]] = {}
        for record in records:
            owners = resolve_record_owners(record, histories_by_ip, device_by_id)
            if len(owners) != 1:
                continue
            raw_key = "|".join(
                (
                    provider.provider_id,
                    record.client,
                    _utc(record.timestamp).isoformat(),
                    record.domain,
                    record.query_type or "",
                )
            )
            key = hashlib.sha256(raw_key.encode()).hexdigest()
            pending[key] = (owners[0], record)
        existing = {
            hashlib.sha256(
                "|".join(
                    (
                        activity.provider_id,
                        activity.source_ip or "",
                        _utc(activity.timestamp).isoformat(),
                        activity.domain,
                        activity.query_type or "",
                    )
                ).encode()
            ).hexdigest()
            for activity in (
                await session.scalars(
                    select(InternetActivity).where(
                        InternetActivity.provider_id == provider.provider_id
                    )
                )
            ).all()
        }
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
