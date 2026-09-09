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
from models.internet_activity import InternetActivity
from schemas.internet_activity import (
    InternetActivityDiagnosticsResponse,
    InternetActivityListResponse,
    InternetActivityResponse,
    InternetActivitySummaryResponse,
)
from services.providers.dns import DNSCapability
from services.providers.registry import provider_registry

router = APIRouter(prefix="/internet-activity", tags=["internet activity"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
logger = logging.getLogger(__name__)


def _diagnostic_steps() -> list[str]:
    steps = [
        "Run AdGuard Home on a device that current network clients can reach.",
        "Configure the router or each device to use that AdGuard Home address as DNS.",
        "Open a website, then refresh Internet Activity or run another NetWatch scan.",
    ]
    if settings.adguard_dns_port != 53:
        steps.insert(
            1,
            "Move AdGuard DNS to standard port 53; most routers and phones cannot use "
            "a custom DNS port.",
        )
    return steps


@router.get("/diagnostics", response_model=InternetActivityDiagnosticsResponse)
async def internet_activity_diagnostics(
    session: SessionDependency,
) -> InternetActivityDiagnosticsResponse:
    provider = provider_registry.dns
    health = await provider.test_connection()
    base = {
        "provider_id": provider.provider_id,
        "provider_name": provider.display_name,
        "provider_status": health.status.value,
        "network_cidr": settings.netwatch_subnet,
        "dns_port": settings.adguard_dns_port,
        "records_checked": 0,
        "matched_records": 0,
        "matched_devices": 0,
        "unmatched_clients": [],
        "steps": _diagnostic_steps(),
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

    device_by_ip = {
        device.ip_address: device.id
        for device in (
            await session.scalars(
                select(Device).where(
                    Device.source == active_source(),
                    Device.network_cidr == settings.netwatch_subnet,
                )
            )
        ).all()
    }
    try:
        records = await provider.query_history(limit=500)
    except Exception:
        logger.exception("Could not inspect DNS provider query history")
        return InternetActivityDiagnosticsResponse(
            **base,
            status="provider_error",
            message="The DNS provider is connected but its query history could not be read.",
        )

    matched = [record for record in records if record.client in device_by_ip]
    matched_device_ids = {device_by_ip[record.client] for record in matched}
    unmatched_clients = sorted(
        {record.client for record in records if record.client and record.client not in device_by_ip}
    )[:20]
    result = {
        **base,
        "records_checked": len(records),
        "matched_records": len(matched),
        "matched_devices": len(matched_device_ids),
        "unmatched_clients": unmatched_clients,
    }
    if not records:
        return InternetActivityDiagnosticsResponse(
            **result,
            status="no_queries",
            message="AdGuard Home is connected, but its query log has no DNS requests yet.",
        )
    if not matched:
        port_note = (
            f" The configured DNS listener uses port {settings.adguard_dns_port}, "
            "not standard port 53."
            if settings.adguard_dns_port != 53
            else ""
        )
        return InternetActivityDiagnosticsResponse(
            **result,
            status="unmatched_clients",
            message=(
                "AdGuard Home has queries, but none came from devices discovered on "
                "the current network."
                + port_note
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
