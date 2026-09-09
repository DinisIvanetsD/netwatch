import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.control import AccessAudit
from models.device import Device, DeviceSource
from services.providers.common import CapabilityUnavailableError
from services.providers.network import NetworkCapability
from services.providers.registry import provider_registry

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ControlResult:
    changed: bool
    message: str


class NetworkControlActionError(RuntimeError):
    pass


def _identifier(device: Device) -> str:
    return device.mac_address or device.ip_address


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
    identifier = _identifier(device)
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=duration_minutes) if duration_minutes is not None else None

    idempotent_messages = {
        "pause_internet": device.internet_access == "paused" and device.paused_until == expires_at,
        "resume_internet": device.internet_access == "allowed",
        "block_internet": device.internet_access == "blocked",
        "quarantine": device.trust_state == "quarantined",
        "release": device.trust_state != "quarantined",
        "block_device": device.trust_state == "blocked",
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
    elif action == "resume_internet":
        device.internet_access = "allowed"
        device.paused_until = None
    elif action == "block_internet":
        device.internet_access = "blocked"
        device.paused_until = None
    elif action == "quarantine":
        device.trust_state = "quarantined"
        device.internet_access = "blocked"
        device.lan_access = "restricted"
        device.quarantine_reason = "Administrator action"
        device.quarantined_at = now
    elif action == "release":
        device.trust_state = "unknown"
        device.internet_access = "allowed"
        device.lan_access = "allowed"
        device.quarantine_reason = None
        device.quarantined_at = None
    elif action == "block_device":
        device.trust_state = "blocked"
        device.internet_access = "blocked"
        device.lan_access = "blocked"
        device.paused_until = None

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


async def resume_expired_pauses(session: AsyncSession, source: DeviceSource) -> int:
    now = datetime.now(UTC)
    devices = list(
        (
            await session.scalars(
                select(Device).where(
                    Device.source == source,
                    Device.network_cidr == settings.netwatch_subnet,
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
