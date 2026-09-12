import logging
from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import active_source
from core.config import settings
from database.session import get_session
from models.device import Device
from models.device_address import DeviceAddressHistory
from models.internet_activity import InternetActivity
from schemas.internet_activity import (
    InternetActivityDiagnosticsResponse,
    InternetActivityListResponse,
    InternetActivityResponse,
    InternetActivitySummaryResponse,
)
from services.activity.sync import resolve_record_owners
from services.integrations import get_technitium_integration
from services.providers.dns import DNSCapability
from services.providers.registry import provider_registry

router = APIRouter(prefix="/internet-activity", tags=["internet activity"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
logger = logging.getLogger(__name__)


def _diagnostic_steps(dns_port: int) -> list[str]:
    steps = [
        "Run Technitium DNS Server on a device that current network clients can reach.",
        "Configure the router or each device to use that Technitium address as DNS.",
        "Open a website, then refresh Internet Activity or run another NetWatch scan.",
    ]
    if dns_port != 53:
        steps.insert(
            1,
            "Move Technitium DNS to standard port 53; most routers and phones cannot use "
            "a custom DNS port.",
        )
    return steps


@router.get("/diagnostics", response_model=InternetActivityDiagnosticsResponse)
async def internet_activity_diagnostics(
    session: SessionDependency,
) -> InternetActivityDiagnosticsResponse:
    provider = provider_registry.dns
    health = await provider.test_connection()
    integration = await get_technitium_integration(session)
    dns_port = (
        int(integration.configuration.get("dns_port", settings.technitium_dns_port))
        if integration is not None
        else settings.technitium_dns_port
    )
    base = {
        "provider_id": provider.provider_id,
        "provider_name": provider.display_name,
        "provider_status": health.status.value,
        "network_cidr": settings.netwatch_subnet,
        "dns_port": dns_port,
        "records_checked": 0,
        "matched_records": 0,
        "matched_devices": 0,
        "attributed_records": 0,
        "unmatched_records": 0,
        "ambiguous_records": 0,
        "ambiguous_clients": [],
        "unmatched_clients": [],
        "steps": _diagnostic_steps(dns_port),
    }
    if not provider.supports(DNSCapability.QUERY_HISTORY):
        return InternetActivityDiagnosticsResponse(
            **base,
            status="not_configured",
            message="Connect a supported DNS provider before Internet activity can be collected.",
        )
    if health.status.value != "connected":
        return InternetActivityDiagnosticsResponse(
            **base,
            status="provider_error",
            message=health.message,
        )

    devices = list(
        (
            await session.scalars(
                select(Device).where(
                    Device.source == active_source(),
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
    try:
        records = await provider.query_history(limit=500)
    except Exception:
        logger.exception("Could not inspect DNS provider query history")
        return InternetActivityDiagnosticsResponse(
            **base,
            status="provider_error",
            message="The DNS provider is connected but its query history could not be read.",
        )

    attributed = []
    unmatched = []
    ambiguous = []
    for record in records:
        owners = resolve_record_owners(record, histories_by_ip, device_by_id)
        if len(owners) == 1:
            attributed.append((record, owners[0]))
        elif len(owners) > 1:
            ambiguous.append(record)
        else:
            unmatched.append(record)
    matched_device_ids = {device.id for _, device in attributed}
    unmatched_clients = sorted({record.client for record in unmatched if record.client})[:20]
    ambiguous_clients = sorted({record.client for record in ambiguous if record.client})[:20]
    result = {
        **base,
        "records_checked": len(records),
        "matched_records": len(attributed),
        "matched_devices": len(matched_device_ids),
        "attributed_records": len(attributed),
        "unmatched_records": len(unmatched),
        "ambiguous_records": len(ambiguous),
        "ambiguous_clients": ambiguous_clients,
        "unmatched_clients": unmatched_clients,
    }
    if not records:
        return InternetActivityDiagnosticsResponse(
            **result,
            status="no_queries",
            message="Technitium is connected, but its query log has no DNS requests yet.",
        )
    if not attributed:
        port_note = (
            f" The configured DNS listener uses port {dns_port}, not standard port 53."
            if dns_port != 53
            else ""
        )
        return InternetActivityDiagnosticsResponse(
            **result,
            status="unmatched_clients",
            message=(
                "Technitium has queries, but none came from devices discovered on "
                "the current network." + port_note
            ),
        )
    return InternetActivityDiagnosticsResponse(
        **result,
        status="ready",
        message="DNS activity is reaching NetWatch and matching current-network devices.",
    )


@router.get("", response_model=InternetActivityListResponse)
async def list_internet_activity(
    session: SessionDependency,
    device_id: int | None = None,
    category: Annotated[str | None, Query(min_length=1, max_length=40)] = None,
    blocked: bool | None = None,
    search: Annotated[str | None, Query(min_length=1, max_length=253)] = None,
    hours: Annotated[int, Query(ge=1, le=24 * 90)] = 24,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=200)] = 50,
) -> InternetActivityListResponse:
    filters = [
        Device.source == active_source(),
        Device.network_cidr == settings.netwatch_subnet,
        Device.network_id == settings.netwatch_network_id,
        InternetActivity.timestamp >= datetime.now(UTC) - timedelta(hours=hours),
    ]
    if device_id is not None:
        filters.append(InternetActivity.device_id == device_id)
    if category:
        filters.append(InternetActivity.category == category)
    if blocked is not None:
        filters.append(InternetActivity.blocked.is_(blocked))
    if search:
        filters.append(InternetActivity.domain.ilike(f"%{search}%"))
    rows = (
        await session.execute(
            select(
                InternetActivity,
                func.coalesce(Device.name, Device.hostname, Device.ip_address),
            )
            .join(Device, Device.id == InternetActivity.device_id)
            .where(*filters)
            .order_by(InternetActivity.timestamp.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()
    total = int(
        (
            await session.scalar(
                select(func.count())
                .select_from(InternetActivity)
                .join(Device, Device.id == InternetActivity.device_id)
                .where(*filters)
            )
        )
        or 0
    )
    return InternetActivityListResponse(
        items=[
            InternetActivityResponse.model_validate(item).model_copy(
                update={"device_name": device_name}
            )
            for item, device_name in rows
        ],
        total=total,
        page=page,
        per_page=per_page,
        pages=ceil(total / per_page) if total else 0,
    )


@router.get("/summary", response_model=InternetActivitySummaryResponse)
async def internet_activity_summary(
    session: SessionDependency,
    hours: Annotated[int, Query(ge=1, le=24 * 90)] = 24,
    device_id: int | None = None,
) -> InternetActivitySummaryResponse:
    since = datetime.now(UTC) - timedelta(hours=hours)
    filters = [
        Device.source == active_source(),
        Device.network_cidr == settings.netwatch_subnet,
        Device.network_id == settings.netwatch_network_id,
        InternetActivity.timestamp >= since,
    ]
    if device_id is not None:
        filters.append(InternetActivity.device_id == device_id)
    total = int(
        (
            await session.scalar(
                select(func.count())
                .select_from(InternetActivity)
                .join(Device, Device.id == InternetActivity.device_id)
                .where(*filters)
            )
        )
        or 0
    )
    blocked = int(
        (
            await session.scalar(
                select(func.count())
                .select_from(InternetActivity)
                .join(Device, Device.id == InternetActivity.device_id)
                .where(*filters, InternetActivity.blocked.is_(True))
            )
        )
        or 0
    )
    active_devices = int(
        (
            await session.scalar(
                select(func.count(func.distinct(InternetActivity.device_id)))
                .join(Device, Device.id == InternetActivity.device_id)
                .where(*filters)
            )
        )
        or 0
    )
    top_domains = (
        await session.execute(
            select(InternetActivity.domain, func.count().label("count"))
            .join(Device, Device.id == InternetActivity.device_id)
            .where(*filters)
            .group_by(InternetActivity.domain)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()
    categories = (
        await session.execute(
            select(InternetActivity.category, func.count().label("count"))
            .join(Device, Device.id == InternetActivity.device_id)
            .where(*filters)
            .group_by(InternetActivity.category)
            .order_by(func.count().desc())
        )
    ).all()
    top_services = (
        await session.execute(
            select(InternetActivity.service, func.count().label("count"))
            .join(Device, Device.id == InternetActivity.device_id)
            .where(*filters, InternetActivity.service.is_not(None))
            .group_by(InternetActivity.service)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()
    return InternetActivitySummaryResponse(
        total_queries=total,
        blocked_queries=blocked,
        active_devices=active_devices,
        top_domains=[{"domain": domain, "count": count} for domain, count in top_domains],
        top_services=[{"service": service, "count": count} for service, count in top_services],
        categories=[{"category": category, "count": count} for category, count in categories],
    )
