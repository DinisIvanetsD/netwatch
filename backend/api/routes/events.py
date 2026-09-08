from datetime import datetime
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.devices import active_source
from database.session import get_session
from models.device import Device
from models.event import Event, EventSeverity, EventType
from schemas.history import EventListResponse, EventResponse

router = APIRouter(prefix="/events", tags=["events"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=EventListResponse)
async def list_events(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 25,
    device_id: int | None = None,
    event_type: Annotated[EventType | None, Query(alias="type")] = None,
    severity: EventSeverity | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> EventListResponse:
    filters = [Event.source == active_source()]
    if device_id is not None:
        filters.append(Event.device_id == device_id)
    if event_type is not None:
        filters.append(Event.type == event_type)
    if severity is not None:
        filters.append(Event.severity == severity)
    if from_time is not None:
        filters.append(Event.timestamp >= from_time)
    if to_time is not None:
        filters.append(Event.timestamp <= to_time)

    rows = (
        await session.execute(
            select(Event, Device.name, Device.hostname, Device.ip_address)
            .outerjoin(Device, Event.device_id == Device.id)
            .where(*filters)
            .order_by(Event.timestamp.desc(), Event.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()
    total = int(
        (await session.scalar(select(func.count()).select_from(Event).where(*filters))) or 0
    )
    items = [
        EventResponse(
            id=event.id,
            device_id=event.device_id,
            device_name=name or hostname or ip_address,
            type=event.type,
            message=event.message,
            severity=event.severity,
            timestamp=event.timestamp,
            metadata=event.metadata_payload,
        )
        for event, name, hostname, ip_address in rows
    ]
    return EventListResponse(
        items=items,
        page=page,
        per_page=per_page,
        total=total,
        pages=ceil(total / per_page) if total else 0,
    )
