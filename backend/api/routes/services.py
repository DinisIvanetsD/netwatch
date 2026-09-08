from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.devices import active_source
from database.repositories.device import DeviceRepository
from database.session import get_session
from models.device import Device
from models.service import Service
from schemas.service import ServiceListResponse, ServiceResponse

router = APIRouter(prefix="/services", tags=["services"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def serialize(service: Service, device: Device) -> ServiceResponse:
    display_name = device.name if device.name != device.ip_address else None
    hostname = device.hostname if device.hostname != device.ip_address else None
    return ServiceResponse(
        id=service.id,
        device_id=device.id,
        device_name=display_name or hostname or "Unnamed device",
        ip_address=device.ip_address,
        port=service.port,
        protocol=service.protocol,
        service_name=service.service_name,
        first_seen=service.first_seen,
        last_seen=service.last_seen,
        active=service.active,
    )


@router.get("", response_model=ServiceListResponse)
async def list_services(
    session: SessionDependency,
    active_only: Annotated[bool, Query()] = True,
) -> ServiceListResponse:
    query = select(Service, Device).join(Device).where(Device.source == active_source())
    if active_only:
        query = query.where(Service.active.is_(True))
    rows = (await session.execute(query.order_by(Service.service_name, Device.name))).all()
    items = [serialize(service, device) for service, device in rows]
    return ServiceListResponse(items=items, total=len(items))


@router.get("/device/{device_id}", response_model=ServiceListResponse)
async def list_device_services(device_id: int, session: SessionDependency) -> ServiceListResponse:
    device = await DeviceRepository(session).get(device_id, source=active_source())
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    services = list(
        (
            await session.scalars(
                select(Service)
                .where(Service.device_id == device_id)
                .order_by(Service.active.desc(), Service.port)
            )
        ).all()
    )
    return ServiceListResponse(
        items=[serialize(service, device) for service in services], total=len(services)
    )
