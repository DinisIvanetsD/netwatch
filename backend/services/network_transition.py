import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import normalize_private_subnet, settings
from models.device import DeviceSource
from models.scan import Scan
from models.setting import AppSetting
from services.control.actions import clear_dns_containment_for_network_switch
from services.control.rules import reconcile_all_rules
from services.providers.registry import provider_registry
from services.realtime.manager import connection_manager

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NetworkTransition:
    previous_subnet: str
    previous_network_id: str
    subnet: str
    network_id: str


async def transition_network(
    session: AsyncSession,
    *,
    subnet: str,
    network_id: str,
    source: DeviceSource,
    actor: str,
    scan_id: int | None = None,
    interface_name: str | None = None,
) -> NetworkTransition | None:
    """Move the active inventory boundary without carrying IP controls across LANs."""

    normalized_subnet = normalize_private_subnet(subnet)
    normalized_id = network_id.strip()
    if not normalized_id or len(normalized_id) > 80:
        raise ValueError("The detected network identity is invalid.")

    previous_subnet = settings.netwatch_subnet
    previous_network_id = settings.netwatch_network_id
    if (
        normalized_subnet == previous_subnet
        and normalized_id == previous_network_id
    ):
        return None

    # External containment is removed before publishing the new scope. A failed
    # cleanup aborts the transition rather than risking an old IP rule on a new LAN.
    await clear_dns_containment_for_network_switch(
        session,
        source,
        previous_subnet,
        previous_network_id,
        actor=actor,
    )
    if scan_id is not None:
        scan = await session.get(Scan, scan_id)
        if scan is not None:
            scan.subnet = normalized_subnet
            scan.network_id = normalized_id
    await session.merge(AppSetting(key="netwatch_subnet", value=normalized_subnet))
    await session.merge(AppSetting(key="netwatch_network_id", value=normalized_id))
    await session.commit()

    settings.netwatch_subnet = normalized_subnet
    settings.netwatch_network_id = normalized_id
    provider_registry.update_network_scope(normalized_subnet)

    try:
        await reconcile_all_rules(session, source)
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Domain-rule reconciliation failed after a network transition")

    transition = NetworkTransition(
        previous_subnet=previous_subnet,
        previous_network_id=previous_network_id,
        subnet=normalized_subnet,
        network_id=normalized_id,
    )
    await connection_manager.broadcast(
        "network.changed",
        {
            "previous_subnet": previous_subnet,
            "previous_network_id": previous_network_id,
            "subnet": normalized_subnet,
            "network_id": normalized_id,
            "interface": interface_name,
        },
    )
    return transition
