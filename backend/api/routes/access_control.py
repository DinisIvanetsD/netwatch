from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import active_source
from database.repositories.device import DeviceRepository
from database.session import get_session
from models.control import AccessAudit, ControlProfile
from models.device import Device
from schemas.control import (
    AccessAuditListResponse,
    AccessAuditResponse,
    AccessOverviewResponse,
    DeviceControlResponse,
    DeviceIdentityUpdate,
    PauseInternetRequest,
)
from schemas.device import DeviceResponse
from services.control.actions import (
    NetworkControlActionError,
    perform_network_action,
    set_trust_state,
)
from services.control.rules import reconcile_profile_rules
from services.providers.network import NetworkCapability
from services.providers.registry import provider_registry
from services.realtime.manager import connection_manager

router = APIRouter(tags=["access control"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


async def _device(session: AsyncSession, device_id: int) -> Device:
    device = await DeviceRepository(session).get(device_id, source=active_source())
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    return device


def _device_response(device: Device) -> DeviceResponse:
    return DeviceResponse.model_validate(device)


@router.get("/access-control", response_model=AccessOverviewResponse)
async def access_overview(session: SessionDependency) -> AccessOverviewResponse:
    devices = list(
        (
            await session.scalars(
                select(Device)
                .where(Device.source == active_source())
                .order_by(Device.last_seen.desc())
            )
        ).all()
    )
    counts = {state: 0 for state in ("trusted", "unknown", "quarantined", "blocked", "ignored")}
    for device in devices:
        counts[device.trust_state] = counts.get(device.trust_state, 0) + 1
    provider = provider_registry.network
    health = await provider.test_connection()
    return AccessOverviewResponse(
        devices=[_device_response(device) for device in devices],
        trusted=counts["trusted"],
        unknown=counts["unknown"],
        quarantined=counts["quarantined"],
        blocked=counts["blocked"],
        ignored=counts["ignored"],
        provider_id=provider.provider_id,
        provider_name=provider.display_name,
        provider_configured=provider.provider_id != "monitoring_only",
        capabilities={
            capability.value: provider.supports(capability) for capability in NetworkCapability
        },
        message=health.message,
    )


@router.get("/access-audit", response_model=AccessAuditListResponse)
async def list_access_audit(
    session: SessionDependency,
    device_id: int | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AccessAuditListResponse:
    filters = [AccessAudit.source == active_source()]
    if device_id is not None:
        filters.append(AccessAudit.device_id == device_id)
    rows = (
        await session.execute(
            select(
                AccessAudit,
                func.coalesce(Device.name, Device.hostname, Device.ip_address),
            )
            .outerjoin(Device, Device.id == AccessAudit.device_id)
            .where(*filters)
            .order_by(AccessAudit.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()
    total = int(
        (await session.scalar(select(func.count()).select_from(AccessAudit).where(*filters))) or 0
    )
    return AccessAuditListResponse(
        items=[
            AccessAuditResponse(
                id=audit.id,
                device_id=audit.device_id,
                device_name=device_name,
                action=audit.action,
                actor=audit.actor,
                result=audit.result,
                provider_id=audit.provider_id,
                message=audit.message,
                expires_at=audit.expires_at,
                metadata=audit.metadata_payload,
                created_at=audit.created_at,
            )
            for audit, device_name in rows
        ],
        total=total,
        page=page,
        per_page=per_page,
        pages=ceil(total / per_page) if total else 0,
    )


@router.patch("/devices/{device_id}/identity", response_model=DeviceResponse)
async def update_device_identity(
    device_id: int,
    payload: DeviceIdentityUpdate,
    session: SessionDependency,
) -> DeviceResponse:
    device = await _device(session, device_id)
    previous_profile = device.profile_id
    values = payload.model_dump(exclude_unset=True)
    if "profile_id" in values and values["profile_id"] is not None:
        profile = await session.scalar(
            select(ControlProfile.id).where(
                ControlProfile.id == values["profile_id"],
                ControlProfile.source == active_source(),
            )
        )
        if profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    for key, value in values.items():
        setattr(device, key, value)
    await session.flush()
    affected_profiles = {previous_profile, device.profile_id}.difference({None})
    for profile_id in affected_profiles:
        await reconcile_profile_rules(session, profile_id, active_source())
    await session.commit()
    await session.refresh(device)
    await connection_manager.broadcast("device.updated", {"device_id": device.id})
    return _device_response(device)


async def _trust_action(
    device_id: int,
    state: str,
    session: AsyncSession,
) -> DeviceControlResponse:
    device = await _device(session, device_id)
    if device.trust_state in {"quarantined", "blocked"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Release this device through the network provider before changing its trust state."
            ),
        )
    result = await set_trust_state(session, device, state)
    await session.commit()
    await session.refresh(device)
    await connection_manager.broadcast(
        f"device.{state}", {"device_id": device.id, "message": result.message}
    )
    return DeviceControlResponse(
        changed=result.changed,
        message=result.message,
        device=_device_response(device),
    )


@router.post("/devices/{device_id}/trust", response_model=DeviceControlResponse)
async def trust_device(device_id: int, session: SessionDependency) -> DeviceControlResponse:
    return await _trust_action(device_id, "trusted", session)


@router.post("/devices/{device_id}/ignore", response_model=DeviceControlResponse)
async def ignore_device(device_id: int, session: SessionDependency) -> DeviceControlResponse:
    return await _trust_action(device_id, "ignored", session)


async def _network_action(
    device_id: int,
    action: str,
    event: str,
    session: AsyncSession,
    *,
    duration_minutes: int | None = None,
) -> DeviceControlResponse:
    device = await _device(session, device_id)
    try:
        result = await perform_network_action(
            session,
            device,
            action,
            duration_minutes=duration_minutes,
        )
    except NetworkControlActionError as error:
        await session.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    await session.commit()
    await session.refresh(device)
    await connection_manager.broadcast(event, {"device_id": device.id, "message": result.message})
    return DeviceControlResponse(
        changed=result.changed,
        message=result.message,
        device=_device_response(device),
    )


@router.post("/devices/{device_id}/pause-internet", response_model=DeviceControlResponse)
async def pause_internet(
    device_id: int,
    payload: PauseInternetRequest,
    session: SessionDependency,
) -> DeviceControlResponse:
    return await _network_action(
        device_id,
        "pause_internet",
        "internet.paused",
        session,
        duration_minutes=payload.duration_minutes,
    )


@router.post("/devices/{device_id}/resume-internet", response_model=DeviceControlResponse)
async def resume_internet(device_id: int, session: SessionDependency) -> DeviceControlResponse:
    return await _network_action(device_id, "resume_internet", "internet.resumed", session)


@router.post("/devices/{device_id}/block-internet", response_model=DeviceControlResponse)
async def block_internet(device_id: int, session: SessionDependency) -> DeviceControlResponse:
    return await _network_action(device_id, "block_internet", "internet.blocked", session)


@router.post("/devices/{device_id}/quarantine", response_model=DeviceControlResponse)
async def quarantine_device(device_id: int, session: SessionDependency) -> DeviceControlResponse:
    return await _network_action(device_id, "quarantine", "device.quarantined", session)


@router.post("/devices/{device_id}/release", response_model=DeviceControlResponse)
async def release_device(device_id: int, session: SessionDependency) -> DeviceControlResponse:
    return await _network_action(device_id, "release", "device.released", session)


@router.post("/devices/{device_id}/block", response_model=DeviceControlResponse)
async def block_device(device_id: int, session: SessionDependency) -> DeviceControlResponse:
    return await _network_action(device_id, "block_device", "device.blocked", session)
