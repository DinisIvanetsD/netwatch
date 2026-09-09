import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.control import DomainRule
from models.device import Device, DeviceSource
from services.providers.common import CapabilityUnavailableError
from services.providers.dns import DNSCapability, DomainRuleRequest
from services.providers.registry import provider_registry

logger = logging.getLogger(__name__)


class ControlRuleRemovalError(RuntimeError):
    pass


async def _rule_clients(
    session: AsyncSession, rule: DomainRule, source: DeviceSource
) -> tuple[str, ...] | None:
    if rule.scope_type == "global":
        return None
    if rule.scope_type == "device":
        device = await session.scalar(
            select(Device).where(
                Device.id == rule.scope_id,
                Device.source == source,
                Device.network_cidr == settings.netwatch_subnet,
            )
        )
        return (device.ip_address,) if device else ()
    if rule.scope_type == "profile":
        return tuple(
            (
                await session.scalars(
                    select(Device.ip_address)
                    .where(
                        Device.profile_id == rule.scope_id,
                        Device.source == source,
                        Device.network_cidr == settings.netwatch_subnet,
                    )
                    .order_by(Device.ip_address)
                )
            ).all()
        )
    return ()


def _provider_request(rule: DomainRule, clients: tuple[str, ...] | None) -> DomainRuleRequest:
    return DomainRuleRequest(
        domain=rule.domain,
        allow=rule.action == "allow",
        clients=clients or (),
        include_subdomains=rule.include_subdomains,
    )


async def enforce_domain_rule(
    session: AsyncSession, rule: DomainRule, source: DeviceSource
) -> None:
    now = datetime.now(UTC)
    if source == DeviceSource.DEMO:
        rule.provider_rule = None
        rule.enforcement_status = "demo"
        rule.enforcement_error = "Demo policy only; no live DNS provider was changed."
        return
    if rule.expires_at is not None:
        expires_at = (
            rule.expires_at if rule.expires_at.tzinfo else rule.expires_at.replace(tzinfo=UTC)
        )
        if expires_at <= now:
            await expire_domain_rule(rule)
            return

    clients = await _rule_clients(session, rule, source)
    provider = provider_registry.dns
    required = DNSCapability.CLIENT_RULES if clients is not None else DNSCapability.DOMAIN_BLOCKING
    if clients == ():
        if rule.provider_reference and rule.enforcement_status == "active":
            try:
                await provider.remove_managed_domain_rule(rule.provider_reference)
            except Exception as error:
                rule.enforcement_status = "error"
                rule.enforcement_error = str(error)[:300]
                return
        rule.provider_rule = None
        rule.enforcement_status = "pending"
        rule.enforcement_error = "Assign at least one device before this scoped rule can apply."
        return
    if not provider.supports(required):
        rule.enforcement_status = "pending"
        rule.enforcement_error = (
            f"{required.value.replace('_', ' ').title()} is unavailable with "
            f"{provider.display_name}."
        )
        return

    if not rule.provider_reference:
        rule.provider_reference = f"domain-rule-{rule.id}"
    try:
        rendered = await provider.upsert_managed_domain_rule(
            rule.provider_reference, _provider_request(rule, clients)
        )
    except (CapabilityUnavailableError, RuntimeError, ValueError) as error:
        logger.warning("Could not enforce domain rule %s: %s", rule.id, error)
        rule.enforcement_status = "error"
        rule.enforcement_error = str(error)[:300]
        return
    rule.provider_rule = rendered
    rule.enforcement_status = "active"
    rule.enforcement_error = None
    rule.last_applied_at = now


async def remove_domain_rule(rule: DomainRule) -> None:
    if rule.source == DeviceSource.DEMO:
        return
    if not rule.provider_reference or rule.enforcement_status in {"pending", "expired"}:
        return
    provider = provider_registry.dns
    if not provider.supports(DNSCapability.DOMAIN_BLOCKING):
        raise ControlRuleRemovalError(
            "The DNS provider is unavailable; the rule was kept to avoid leaving an orphaned block."
        )
    try:
        await provider.remove_managed_domain_rule(rule.provider_reference)
    except Exception as error:
        raise ControlRuleRemovalError(
            "The DNS provider could not remove this rule, so NetWatch kept the record."
        ) from error


async def expire_domain_rule(rule: DomainRule) -> bool:
    try:
        await remove_domain_rule(rule)
    except ControlRuleRemovalError as error:
        rule.enforcement_status = "error"
        rule.enforcement_error = str(error)
        return False
    rule.enabled = False
    rule.enforcement_status = "expired"
    rule.enforcement_error = None
    rule.provider_rule = None
    return True


async def reconcile_profile_rules(
    session: AsyncSession, profile_id: int, source: DeviceSource
) -> None:
    rules = list(
        (
            await session.scalars(
                select(DomainRule).where(
                    DomainRule.source == source,
                    DomainRule.scope_type == "profile",
                    DomainRule.scope_id == profile_id,
                    DomainRule.enabled.is_(True),
                )
            )
        ).all()
    )
    for rule in rules:
        await enforce_domain_rule(session, rule, source)


async def reconcile_device_rules(
    session: AsyncSession, device_id: int, source: DeviceSource
) -> None:
    device = await session.scalar(
        select(Device).where(
            Device.id == device_id,
            Device.source == source,
            Device.network_cidr == settings.netwatch_subnet,
        )
    )
    profile_ids = [device.profile_id] if device and device.profile_id else []
    rules = list(
        (
            await session.scalars(
                select(DomainRule).where(
                    DomainRule.source == source,
                    DomainRule.enabled.is_(True),
                    (
                        (DomainRule.scope_type == "device") & (DomainRule.scope_id == device_id)
                        | (DomainRule.scope_type == "profile")
                        & (DomainRule.scope_id.in_(profile_ids))
                    ),
                )
            )
        ).all()
    )
    for rule in rules:
        await enforce_domain_rule(session, rule, source)


async def expire_domain_rules(session: AsyncSession, source: DeviceSource) -> int:
    now = datetime.now(UTC)
    rules = list(
        (
            await session.scalars(
                select(DomainRule).where(
                    DomainRule.source == source,
                    DomainRule.enabled.is_(True),
                    DomainRule.expires_at <= now,
                )
            )
        ).all()
    )
    expired = 0
    for rule in rules:
        if await expire_domain_rule(rule):
            expired += 1
    return expired


async def reconcile_all_rules(session: AsyncSession, source: DeviceSource) -> None:
    rules = list(
        (
            await session.scalars(
                select(DomainRule)
                .where(DomainRule.source == source, DomainRule.enabled.is_(True))
                .order_by(DomainRule.id)
            )
        ).all()
    )
    for rule in rules:
        await enforce_domain_rule(session, rule, source)
