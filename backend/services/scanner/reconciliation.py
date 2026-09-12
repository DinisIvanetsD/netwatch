from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.alert import Alert
from models.control import AccessAudit, DomainRule
from models.device import Device, DeviceStatus
from models.device_address import DeviceAddressHistory
from models.event import Event
from models.internet_activity import InternetActivity
from models.metric import DeviceMetric
from models.service import Service
from services.discovery.identity import normalize_mac


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _identity_score(device: Device) -> tuple[int, int, datetime, int]:
    name_is_custom = bool(device.name and device.name not in {device.ip_address, device.hostname})
    identity = (
        (80 if device.owner else 0)
        + (70 if device.profile_id is not None else 0)
        + (40 if device.device_type else 0)
        + (30 if name_is_custom else 0)
        + (10 if device.name else 0)
        + (10 if device.trust_state != "unknown" else 0)
        + (10 if device.internet_access != "allowed" else 0)
        + (10 if device.lan_access != "allowed" else 0)
        + (10 if device.quarantined_at or device.paused_until else 0)
    )
    status_rank = {
        DeviceStatus.ONLINE: 3,
        DeviceStatus.NEW: 2,
        DeviceStatus.UNKNOWN: 1,
        DeviceStatus.OFFLINE: 0,
    }[device.status]
    return identity, status_rank, _utc(device.last_seen), -(device.id or 0)


def _merge_device_fields(keeper: Device, duplicate: Device) -> None:
    keeper.first_seen = min(_utc(keeper.first_seen), _utc(duplicate.first_seen))
    keeper.last_seen = max(_utc(keeper.last_seen), _utc(duplicate.last_seen))
    keeper.is_gateway = keeper.is_gateway or duplicate.is_gateway
    keeper.missed_scans = min(keeper.missed_scans, duplicate.missed_scans)
    keeper.mac_address = normalize_mac(keeper.mac_address or duplicate.mac_address)

    for attribute in ("name", "owner", "device_type", "hostname", "vendor"):
        if not getattr(keeper, attribute) and getattr(duplicate, attribute):
            setattr(keeper, attribute, getattr(duplicate, attribute))
    if keeper.profile_id is None and duplicate.profile_id is not None:
        keeper.profile_id = duplicate.profile_id
    if keeper.trust_state == "unknown" and duplicate.trust_state != "unknown":
        keeper.trust_state = duplicate.trust_state
    if keeper.internet_access == "allowed" and duplicate.internet_access != "allowed":
        keeper.internet_access = duplicate.internet_access
    if keeper.lan_access == "allowed" and duplicate.lan_access != "allowed":
        keeper.lan_access = duplicate.lan_access
    if keeper.paused_until is None or (
        duplicate.paused_until is not None
        and _utc(duplicate.paused_until) > _utc(keeper.paused_until)
    ):
        keeper.paused_until = duplicate.paused_until
    if keeper.quarantined_at is None and duplicate.quarantined_at is not None:
        keeper.quarantined_at = duplicate.quarantined_at
    keeper.quarantine_reason = keeper.quarantine_reason or duplicate.quarantine_reason
    keeper.control_provider_id = keeper.control_provider_id or duplicate.control_provider_id
    keeper.control_identifier = keeper.control_identifier or duplicate.control_identifier

    if _identity_score(duplicate)[1:3] > _identity_score(keeper)[1:3]:
        keeper.status = duplicate.status
        keeper.latency_ms = duplicate.latency_ms


async def _merge_services(session: AsyncSession, keeper_id: int, duplicate_id: int) -> None:
    keeper_services = list(
        (await session.scalars(select(Service).where(Service.device_id == keeper_id))).all()
    )
    duplicate_services = list(
        (await session.scalars(select(Service).where(Service.device_id == duplicate_id))).all()
    )
    by_key = {(service.port, service.protocol): service for service in keeper_services}
    services_to_move: list[Service] = []
    for service in duplicate_services:
        key = (service.port, service.protocol)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = service
            services_to_move.append(service)
            continue
        existing.first_seen = min(_utc(existing.first_seen), _utc(service.first_seen))
        existing.last_seen = max(_utc(existing.last_seen), _utc(service.last_seen))
        existing.active = existing.active or service.active
        await session.delete(service)

    # Delete colliding rows before changing ownership to respect the service unique key.
    await session.flush()
    for service in services_to_move:
        service.device_id = keeper_id


async def _move_device_references(
    session: AsyncSession,
    *,
    keeper: Device,
    duplicate: Device,
) -> None:
    if keeper.id is None or duplicate.id is None:
        raise ValueError("Only persisted devices can be reconciled.")
    await _merge_services(session, keeper.id, duplicate.id)
    for model in (DeviceMetric, Event, Alert, AccessAudit, InternetActivity):
        await session.execute(
            update(model)
            .where(model.device_id == duplicate.id)
            .values(device_id=keeper.id)
            .execution_options(synchronize_session=False)
        )
    await session.execute(
        update(DeviceAddressHistory)
        .where(DeviceAddressHistory.device_id == duplicate.id)
        .values(device_id=keeper.id)
        .execution_options(synchronize_session=False)
    )
    await session.execute(
        update(DomainRule)
        .where(
            DomainRule.source == keeper.source,
            DomainRule.scope_type == "device",
            DomainRule.scope_id == duplicate.id,
        )
        .values(scope_id=keeper.id)
        .execution_options(synchronize_session=False)
    )


async def consolidate_duplicate_devices(
    session: AsyncSession,
    devices: list[Device],
) -> tuple[list[Device], set[int]]:
    """Merge duplicate same-MAC rows within an already network-scoped device list."""
    by_mac: defaultdict[str, list[Device]] = defaultdict(list)
    for device in devices:
        normalized = normalize_mac(device.mac_address)
        if normalized:
            device.mac_address = normalized
            by_mac[normalized].append(device)

    removed_ids: set[int] = set()
    changed_ids: set[int] = set()
    for group in by_mac.values():
        if len(group) < 2:
            continue
        source_networks = {(device.source, device.network_cidr) for device in group}
        if len(source_networks) != 1:
            continue
        keeper = max(group, key=_identity_score)
        if keeper.id is None:
            continue
        for duplicate in group:
            if duplicate is keeper or duplicate.id is None:
                continue
            _merge_device_fields(keeper, duplicate)
            await _move_device_references(session, keeper=keeper, duplicate=duplicate)
            removed_ids.add(duplicate.id)
            await session.delete(duplicate)
        changed_ids.add(keeper.id)

    if removed_ids:
        # Free stale IP unique keys before discovery moves the keeper to its current IP.
        await session.flush()
    return [device for device in devices if device.id not in removed_ids], changed_ids
