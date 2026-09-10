from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.devices import active_source
from database.session import get_session
from models.alert import Alert
from models.device import Device
from models.event import EventSeverity
from schemas.alert import AlertListResponse, AlertResponse, AlertUpdate
from services.network_identity import device_in_current_network

router = APIRouter(prefix="/alerts", tags=["alerts"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def serialize(
    alert: Alert, device_name: str | None, hostname: str | None, ip: str | None
) -> AlertResponse:
    return AlertResponse(
        id=alert.id,
        device_id=alert.device_id,
        device_name=device_name or hostname or ip,
        type=alert.type,
        severity=alert.severity,
        title=alert.title,
        description=alert.description,
        created_at=alert.created_at,
        read=alert.read,
        resolved=alert.resolved,
        resolved_at=alert.resolved_at,
    )


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    session: SessionDependency,
    severity: EventSeverity | None = None,
    unresolved_only: Annotated[bool, Query()] = False,
) -> AlertListResponse:
    filters = [
        Alert.source == active_source(),
        or_(Alert.device_id.is_(None), device_in_current_network()),
    ]
    if severity is not None:
        filters.append(Alert.severity == severity)
    if unresolved_only:
        filters.append(Alert.resolved.is_(False))
    rows = (
        await session.execute(
            select(Alert, Device.name, Device.hostname, Device.ip_address)
            .outerjoin(Device, Alert.device_id == Device.id)
            .where(*filters)
            .order_by(Alert.created_at.desc())
        )
    ).all()
    return AlertListResponse(items=[serialize(*row) for row in rows], total=len(rows))


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int, payload: AlertUpdate, session: SessionDependency
) -> AlertResponse:
    alert = await session.scalar(
        select(Alert)
        .outerjoin(Device, Alert.device_id == Device.id)
        .where(
            Alert.id == alert_id,
            Alert.source == active_source(),
            or_(Alert.device_id.is_(None), device_in_current_network()),
        )
    )
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found.")
    if payload.read is not None:
        alert.read = payload.read
    if payload.resolved is not None:
        alert.resolved = payload.resolved
        alert.resolved_at = datetime.now(UTC) if payload.resolved else None
    await session.commit()
    row = (
        await session.execute(
            select(Alert, Device.name, Device.hostname, Device.ip_address)
            .outerjoin(Device, Alert.device_id == Device.id)
            .where(Alert.id == alert.id)
        )
    ).one()
    return serialize(*row)
