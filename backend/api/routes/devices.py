from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import active_source
from core.config import settings
from database.repositories.device import DeviceRepository
from database.session import get_session
from models.device import DeviceStatus
from models.event import Event
from models.metric import DeviceMetric
from models.service import Service
from schemas.device import DeviceListResponse, DeviceResponse, DeviceSortField, SortOrder
from schemas.history import EventListResponse, EventResponse, MetricListResponse, MetricResponse

router = APIRouter(prefix="/devices", tags=["devices"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=DeviceListResponse)
async def list_devices(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 25,
    device_status: Annotated[DeviceStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    sort_by: DeviceSortField = DeviceSortField.LAST_SEEN,
    sort_order: SortOrder = SortOrder.DESC,
) -> DeviceListResponse:
    repository = DeviceRepository(session)
    devices, total = await repository.list(
        source=active_source(),
        network_cidr=settings.netwatch_subnet,
        network_id=settings.netwatch_network_id,
        page=page,
        per_page=per_page,
        status=device_status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    service_rows = (
        await session.execute(
            select(Service.device_id, Service.port).where(
                Service.device_id.in_([device.id for device in devices]), Service.active.is_(True)
            )
        )
    ).all()
    ports_by_device: dict[int, list[int]] = {}
    for device_id, port in service_rows:
        ports_by_device.setdefault(device_id, []).append(port)
    return DeviceListResponse(
        items=[
            DeviceResponse.model_validate(device).model_copy(
                update={"service_ports": sorted(ports_by_device.get(device.id, []))}
            )
            for device in devices
        ],
        page=page,
        per_page=per_page,
        total=total,
        pages=ceil(total / per_page) if total else 0,
    )


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(device_id: int, session: SessionDependency) -> DeviceResponse:
    device = await DeviceRepository(session).get(
        device_id,
        source=active_source(),
        network_cidr=settings.netwatch_subnet,
        network_id=settings.netwatch_network_id,
    )
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found.",
        )
    ports = list(
        (
            await session.scalars(
                select(Service.port)
                .where(Service.device_id == device.id, Service.active.is_(True))
                .order_by(Service.port)
            )
        ).all()
    )
    return DeviceResponse.model_validate(device).model_copy(update={"service_ports": ports})


@router.get("/{device_id}/metrics", response_model=MetricListResponse)
async def get_device_metrics(
    device_id: int,
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=500)] = 100,
) -> MetricListResponse:
    device = await DeviceRepository(session).get(
        device_id,
        source=active_source(),
        network_cidr=settings.netwatch_subnet,
        network_id=settings.netwatch_network_id,
    )
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    filters = [DeviceMetric.device_id == device_id]
    items = list(
        (
            await session.scalars(
                select(DeviceMetric)
                .where(*filters)
                .order_by(DeviceMetric.timestamp.desc(), DeviceMetric.id.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        ).all()
    )
    total = int(
        (await session.scalar(select(func.count()).select_from(DeviceMetric).where(*filters))) or 0
    )
    return MetricListResponse(
        items=[MetricResponse.model_validate(item) for item in items],
        page=page,
        per_page=per_page,
        total=total,
        pages=ceil(total / per_page) if total else 0,
    )


@router.get("/{device_id}/events", response_model=EventListResponse)
async def get_device_events(
    device_id: int,
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 25,
) -> EventListResponse:
    device = await DeviceRepository(session).get(
        device_id,
        source=active_source(),
        network_cidr=settings.netwatch_subnet,
        network_id=settings.netwatch_network_id,
    )
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    filters = [Event.device_id == device_id, Event.source == active_source()]
    events = list(
        (
            await session.scalars(
                select(Event)
                .where(*filters)
                .order_by(Event.timestamp.desc(), Event.id.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        ).all()
    )
    total = int(
        (await session.scalar(select(func.count()).select_from(Event).where(*filters))) or 0
    )
    return EventListResponse(
        items=[
            EventResponse(
                id=event.id,
                device_id=event.device_id,
                device_name=device.name or device.hostname or device.ip_address,
                type=event.type,
                message=event.message,
                severity=event.severity,
                timestamp=event.timestamp,
                metadata=event.metadata_payload,
            )
            for event in events
        ],
        page=page,
        per_page=per_page,
        total=total,
        pages=ceil(total / per_page) if total else 0,
    )
