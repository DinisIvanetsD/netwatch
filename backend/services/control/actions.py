import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.control import AccessAudit
from models.device import Device, DeviceSource, DeviceStatus
from services.providers.common import CapabilityUnavailableError
from services.providers.network import (
    DNSContainmentNetworkProvider,
    NetworkCapability,
    NetworkControlProvider,
)
from services.providers.registry import provider_registry

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ControlResult:
    changed: bool
    message: str


class NetworkControlActionError(RuntimeError):
    pass


async def _require_current_ip_owner(
    session: AsyncSession,
    device: Device,
    provider: NetworkControlProvider,
    action: str,
) -> None:
    """Prevent an IP-based provider from acting on stale DHCP history."""

    if provider.identifier_kind != "ip" or action not in {
        "pause_internet",
        "block_internet",
        "quarantine",
        "block_device",
    }:
        return
    if (
        device.source != DeviceSource.LIVE
        or device.status == DeviceStatus.OFFLINE
        or device.network_cidr != settings.netwatch_subnet
        or device.network_id != settings.netwatch_network_id
    ):
        raise NetworkControlActionError(
            "This device is not a current, online owner of the monitored network. "
            "Run a scan before applying an IP-based control."
        )
    owners = list(
        (
            await session.scalars(
                select(Device).where(
                    Device.source == DeviceSource.LIVE,
                    Device.network_cidr == settings.netwatch_subnet,
                    Device.network_id == settings.netwatch_network_id,
                    Device.ip_address == device.ip_address,
                    Device.status != DeviceStatus.OFFLINE,
                )
            )
        ).all()
    )
    if len(owners) != 1 or owners[0].id != device.id:
        raise NetworkControlActionError(
            "NetWatch cannot prove that this device currently owns its IP address. "
            "Run a scan and select the current device record."
        )


def _identifier(device: Device, provider: NetworkControlProvider) -> str:
    if provider.identifier_kind == "ip":
        return device.ip_address
    if provider.identifier_kind == "mac":
        if not device.mac_address:
            raise NetworkControlActionError(
                f"{provider.display_name} requires a stable device MAC address."
            )
        return device.mac_address
    return device.mac_address or device.ip_address


def _action_identifier(
    device: Device, provider: NetworkControlProvider, action: str
) -> str:
    if action in {"resume_internet", "release"} and device.control_identifier:
        if device.control_provider_id != provider.provider_id:
            raise NetworkControlActionError(
                f"This action was applied by {device.control_provider_id}; restore that "
                "provider before releasing it."
            )
        return device.control_identifier
    return _identifier(device, provider)


def _audit(
    device: Device,
    *,
    action: str,
    actor: str,
    result: str,
    message: str,
    expires_at: datetime | None = None,
) -> AccessAudit:
    return AccessAudit(
        device_id=device.id,
        source=device.source,
        action=action,
        actor=actor,
        result=result,
        provider_id=provider_registry.network.provider_id,
        message=message,
        expires_at=expires_at,
        metadata_payload={"ip_address": device.ip_address},
    )


async def set_trust_state(
    session: AsyncSession, device: Device, state: str, *, actor: str = "administrator"
) -> ControlResult:
    if state not in {"trusted", "unknown", "ignored"}:
        raise ValueError("This trust state requires a network-control action")
    if device.trust_state == state:
        message = f"{device.name or device.ip_address} is already marked {state}."
        session.add(
            _audit(
                device, action=f"device.{state}", actor=actor, result="no_change", message=message
            )
        )
        return ControlResult(False, message)
    device.trust_state = state
    message = f"{device.name or device.ip_address} was marked {state}."
    session.add(
        _audit(device, action=f"device.{state}", actor=actor, result="completed", message=message)
    )
    return ControlResult(True, message)


async def perform_network_action(
    session: AsyncSession,
    device: Device,
    action: str,
    *,
    duration_minutes: int | None = None,
    actor: str = "administrator",
) -> ControlResult:
    provider = provider_registry.network
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=duration_minutes) if duration_minutes is not None else None
    await _require_current_ip_owner(session, device, provider, action)
    current_identifier = _identifier(device, provider)
    applied_to_current_identifier = (
        device.control_provider_id == provider.provider_id
        and device.control_identifier == current_identifier
    )

    idempotent_messages = {
        "pause_internet": device.internet_access == "paused"
        and device.paused_until == expires_at
        and applied_to_current_identifier,
        "resume_internet": device.internet_access == "allowed"
        and device.control_identifier is None,
        "block_internet": device.internet_access == "blocked"
        and applied_to_current_identifier,
        "quarantine": device.trust_state == "quarantined"
        and applied_to_current_identifier,
        "release": device.trust_state != "quarantined",
        "block_device": device.trust_state == "blocked" and applied_to_current_identifier,
    }
    if idempotent_messages.get(action):
        message = f"No change was needed for {device.name or device.ip_address}."
        session.add(
            _audit(
                device,
                action=action,
                actor=actor,
                result="no_change",
                message=message,
                expires_at=expires_at,
            )
        )
        return ControlResult(False, message)

    try:
        identifier = _action_identifier(device, provider, action)
        if action == "pause_internet":
            provider.require(NetworkCapability.BLOCK_INTERNET)
            provider_result = await provider.block_internet(identifier)
        elif action == "resume_internet":
            provider.require(NetworkCapability.UNBLOCK_INTERNET)
            provider_result = await provider.unblock_internet(identifier)
        elif action == "block_internet":
            provider.require(NetworkCapability.BLOCK_INTERNET)
            provider_result = await provider.block_internet(identifier)
        elif action == "quarantine":
            provider.require(NetworkCapability.QUARANTINE_DEVICE)
            provider_result = await provider.quarantine_device(identifier)
        elif action == "release":
            provider.require(NetworkCapability.RELEASE_DEVICE)
            provider_result = await provider.release_device(identifier)
        elif action == "block_device":
            provider.require(NetworkCapability.FIREWALL_RULES)
            provider_result = await provider.block_device(identifier)
        else:
            raise ValueError("Unknown network control action")
    except (CapabilityUnavailableError, RuntimeError, ValueError) as error:
        message = str(error)
        session.add(
            _audit(
                device,
                action=action,
                actor=actor,
                result="failed",
                message=message,
                expires_at=expires_at,
            )
        )
        raise NetworkControlActionError(message) from error

    if action == "pause_internet":
        device.internet_access = "paused"
        device.paused_until = expires_at
        device.control_provider_id = provider.provider_id
        device.control_identifier = identifier
    elif action == "resume_internet":
        device.internet_access = "allowed"
        device.paused_until = None
        device.control_provider_id = None
        device.control_identifier = None
    elif action == "block_internet":
        device.internet_access = "blocked"
        device.paused_until = None
        device.control_provider_id = provider.provider_id
        device.control_identifier = identifier
    elif action == "quarantine":
        device.trust_state = "quarantined"
        device.internet_access = "blocked"
        device.lan_access = "restricted"
        device.quarantine_reason = "Administrator action"
        device.quarantined_at = now
        device.control_provider_id = provider.provider_id
        device.control_identifier = identifier
    elif action == "release":
        device.trust_state = "unknown"
        device.internet_access = "allowed"
        device.lan_access = "allowed"
        device.quarantine_reason = None
        device.quarantined_at = None
        device.control_provider_id = None
        device.control_identifier = None
    elif action == "block_device":
        device.trust_state = "blocked"
        device.internet_access = "blocked"
        device.lan_access = "blocked"
        device.paused_until = None
        device.control_provider_id = provider.provider_id
        device.control_identifier = identifier

    session.add(
        _audit(
            device,
            action=action,
            actor=actor,
            result="completed",
            message=provider_result.message,
            expires_at=expires_at,
        )
    )
    return ControlResult(provider_result.changed, provider_result.message)


async def reconcile_network_control_identifier(
    session: AsyncSession,
    device: Device,
    previous_identifier: str,
    *,
    actor: str = "scanner",
) -> bool:
    """Compatibility wrapper for a single-device coordinated reconciliation."""

    if device.control_identifier != previous_identifier:
        return False
    changed = await reconcile_network_control_identifiers(
        session,
        [device],
        observed_device_ids={device.id} if device.id is not None else set(),
        actor=actor,
    )
    return changed > 0


def _clear_ip_control(device: Device) -> None:
    device.internet_access = "allowed"
    device.paused_until = None
    device.control_provider_id = None
    device.control_identifier = None


async def reconcile_network_control_identifiers(
    session: AsyncSession,
    devices: list[Device],
    *,
    observed_device_ids: set[int],
    actor: str = "scanner",
) -> int:
    """Reconcile all IP controls in two phases to handle swaps and DHCP reuse safely."""

    provider = provider_registry.network
    if provider.identifier_kind != "ip":
        return 0

    controlled = [
        device
        for device in devices
        if device.control_provider_id == provider.provider_id
        and device.control_identifier
        and device.internet_access in {"paused", "blocked"}
    ]
    if not controlled:
        return 0

    observed_by_ip: dict[str, list[Device]] = {}
    for device in devices:
        if device.id is not None and device.id in observed_device_ids:
            observed_by_ip.setdefault(device.ip_address, []).append(device)

    moves: list[tuple[Device, str, str]] = []
    displaced: list[tuple[Device, str]] = []
    for device in controlled:
        previous = device.control_identifier
        is_observed = device.id is not None and device.id in observed_device_ids
        current_owners = observed_by_ip.get(device.ip_address, [])
        unique_current_owner = len(current_owners) == 1 and current_owners[0] is device
        previous_owners = observed_by_ip.get(previous, [])
        previous_claimed_by_other = any(owner is not device for owner in previous_owners)
        if (
            not is_observed
            and previous_claimed_by_other
            or is_observed
            and not unique_current_owner
        ):
            displaced.append((device, previous))
        elif is_observed and previous != device.ip_address:
            moves.append((device, previous, device.ip_address))

    release_targets = {previous for _, previous, _ in moves}
    release_targets.update(previous for _, previous in displaced)
    if not release_targets:
        return 0

    release_failed = False
    for previous in sorted(release_targets):
        try:
            await provider.unblock_internet(previous)
        except (CapabilityUnavailableError, RuntimeError, ValueError) as error:
            release_failed = True
            for device in controlled:
                if device.control_identifier != previous:
                    continue
                session.add(
                    _audit(
                        device,
                        action="control.identifier_changed",
                        actor=actor,
                        result="failed",
                        message=(
                            f"Could not remove {provider.display_name} control from previous "
                            f"address {previous}: {error}. NetWatch will retry on the next scan."
                        ),
                    )
                )

    # Do not apply any new targets after a partial release set. Keeping the old
    # identifiers records a pending mismatch so the next scan retries the whole set.
    if release_failed:
        return 0

    changed = 0
    for device, previous in displaced:
        _clear_ip_control(device)
        changed += 1
        session.add(
            _audit(
                device,
                action="control.identifier_changed",
                actor=actor,
                result="completed",
                message=(
                    f"DNS-only control was removed from {previous} because another device "
                    "now owns that address. The previous device is no longer shown as blocked."
                ),
            )
        )

    for device, previous, desired in moves:
        try:
            result = await provider.block_internet(desired)
        except (CapabilityUnavailableError, RuntimeError, ValueError) as error:
            _clear_ip_control(device)
            session.add(
                _audit(
                    device,
                    action="control.identifier_changed",
                    actor=actor,
                    result="failed",
                    message=(
                        f"Control was removed from recycled address {previous}, but could not "
                        f"be applied to {desired}: {error}"
                    ),
                )
            )
            continue
        device.control_identifier = desired
        changed += 1
        session.add(
            _audit(
                device,
                action="control.identifier_changed",
                actor=actor,
                result="completed",
                message=result.message,
                expires_at=device.paused_until,
            )
        )
    return changed


async def clear_dns_containment_for_network_switch(
    session: AsyncSession,
    source: DeviceSource,
    network_cidr: str,
    network_id: str,
    *,
    actor: str = "scanner",
) -> int:
    provider = provider_registry.network
    if not isinstance(provider, DNSContainmentNetworkProvider):
        return 0

    devices = list(
        (
            await session.scalars(
                select(Device).where(
                    Device.source == source,
                    Device.network_cidr == network_cidr,
                    Device.network_id == network_id,
                    or_(
                        Device.control_provider_id == provider.provider_id,
                        Device.internet_access.in_(("paused", "blocked")),
                        Device.trust_state.in_(("quarantined", "blocked")),
                    ),
                )
            )
        ).all()
    )
    if not devices:
        return 0
    await provider.clear_all()
    for device in devices:
        previous_identifier = device.control_identifier
        device.internet_access = "allowed"
        device.paused_until = None
        device.control_provider_id = None
        device.control_identifier = None
        session.add(
            _audit(
                device,
                action="control.network_changed",
                actor=actor,
                result="completed",
                message=(
                    "DNS-only containment was removed because NetWatch changed network "
                    f"scope; previous identifier: {previous_identifier or 'unknown'}."
                ),
            )
        )
    return len(devices)


async def resume_expired_pauses(session: AsyncSession, source: DeviceSource) -> int:
    now = datetime.now(UTC)
    devices = list(
        (
            await session.scalars(
                select(Device).where(
                    Device.source == source,
                    Device.network_cidr == settings.netwatch_subnet,
                    Device.network_id == settings.netwatch_network_id,
                    Device.internet_access == "paused",
                    Device.paused_until.is_not(None),
                    Device.paused_until <= now,
                )
            )
        ).all()
    )
    resumed = 0
    for device in devices:
        try:
            await perform_network_action(session, device, "resume_internet", actor="system")
        except NetworkControlActionError:
            logger.warning("Could not resume expired Internet pause for device %s", device.id)
        else:
            resumed += 1
    return resumed


async def apply_new_device_policy(session: AsyncSession, devices: list[Device]) -> None:
    action = {
        "quarantine_alert": "quarantine",
        "block_alert": "block_device",
    }.get(settings.new_device_policy)
    if action is None:
        return
    for device in devices:
        try:
            await perform_network_action(session, device, action, actor="policy")
        except NetworkControlActionError:
            logger.warning(
                "New-device policy could not apply %s to device %s with the current provider",
                action,
                device.id,
            )
