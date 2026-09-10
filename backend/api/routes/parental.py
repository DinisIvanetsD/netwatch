from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import active_source
from core.config import settings
from database.session import get_session
from models.control import AccessSchedule, ControlProfile, DomainRule
from models.device import Device
from models.internet_activity import InternetActivity
from schemas.control import (
    AccessScheduleResponse,
    ControlProfileCreate,
    ControlProfileListResponse,
    ControlProfileResponse,
    ControlProfileUpdate,
    DomainRuleCreate,
    DomainRuleResponse,
    ProfileDeviceAssignment,
    RuleScope,
    ScheduleReplaceRequest,
)
from services.control.constants import CATEGORY_LABELS
from services.control.rules import (
    ControlRuleRemovalError,
    enforce_domain_rule,
    reconcile_profile_rules,
    remove_domain_rule,
)
from services.control.schedules import evaluate_schedule
from services.realtime.manager import connection_manager

router = APIRouter(prefix="/parental", tags=["parental controls"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


async def _get_profile(session: AsyncSession, profile_id: int) -> ControlProfile:
    profile = await session.scalar(
        select(ControlProfile).where(
            ControlProfile.id == profile_id,
            ControlProfile.source == active_source(),
        )
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found.")
    return profile


async def _profile_response(
    session: AsyncSession, profile: ControlProfile
) -> ControlProfileResponse:
    schedules = list(
        (
            await session.scalars(
                select(AccessSchedule)
                .where(AccessSchedule.profile_id == profile.id)
                .order_by(AccessSchedule.weekday, AccessSchedule.start_minute)
            )
        ).all()
    )
    rules = list(
        (
            await session.scalars(
                select(DomainRule)
                .where(
                    DomainRule.source == active_source(),
                    DomainRule.scope_type == RuleScope.PROFILE.value,
                    DomainRule.scope_id == profile.id,
                )
                .order_by(DomainRule.created_at.desc())
            )
        ).all()
    )
    device_ids = list(
        (
            await session.scalars(
                select(Device.id)
                .where(
                    Device.source == active_source(),
                    Device.network_cidr == settings.netwatch_subnet,
                    Device.network_id == settings.netwatch_network_id,
                    Device.profile_id == profile.id,
                )
                .order_by(Device.id)
            )
        ).all()
    )
    local_now = datetime.now(UTC).astimezone(ZoneInfo(settings.netwatch_timezone))
    start_of_day = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
    activity_scope = [InternetActivity.profile_id == profile.id]
    if device_ids:
        activity_scope.append(InternetActivity.device_id.in_(device_ids))
    blocked_today = int(
        (
            await session.scalar(
                select(func.count())
                .select_from(InternetActivity)
                .join(Device, Device.id == InternetActivity.device_id)
                .where(
                    Device.source == active_source(),
                    Device.network_cidr == settings.netwatch_subnet,
                    Device.network_id == settings.netwatch_network_id,
                    InternetActivity.blocked.is_(True),
                    InternetActivity.timestamp >= start_of_day,
                    or_(*activity_scope),
                )
            )
        )
        or 0
    )
    schedule_state = evaluate_schedule(
        profile,
        schedules,
        now=datetime.now(UTC),
        timezone=settings.netwatch_timezone,
    )
    return ControlProfileResponse(
        id=profile.id,
        name=profile.name,
        description=profile.description,
        internet_enabled=profile.internet_enabled,
        safe_search_enabled=profile.safe_search_enabled,
        blocked_categories=profile.blocked_categories,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        device_ids=device_ids,
        device_count=len(device_ids),
        blocked_requests_today=blocked_today,
        schedules=[AccessScheduleResponse.model_validate(item) for item in schedules],
        domain_rules=[DomainRuleResponse.model_validate(item) for item in rules],
        schedule_state=schedule_state.state,
        next_schedule_change=schedule_state.next_change,
    )


@router.get("/profiles", response_model=ControlProfileListResponse)
async def list_profiles(session: SessionDependency) -> ControlProfileListResponse:
    profiles = list(
        (
            await session.scalars(
                select(ControlProfile)
                .where(ControlProfile.source == active_source())
                .order_by(ControlProfile.name)
            )
        ).all()
    )
    return ControlProfileListResponse(
        items=[await _profile_response(session, profile) for profile in profiles],
        categories=CATEGORY_LABELS,
    )


@router.post(
    "/profiles",
    response_model=ControlProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_profile(
    payload: ControlProfileCreate, session: SessionDependency
) -> ControlProfileResponse:
    duplicate = await session.scalar(
        select(ControlProfile.id).where(
            ControlProfile.source == active_source(),
            func.lower(ControlProfile.name) == payload.name.lower(),
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A profile with this name already exists.",
        )
    profile = ControlProfile(source=active_source(), **payload.model_dump())
    session.add(profile)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A profile with this name already exists.",
        ) from error
    await session.refresh(profile)
    await connection_manager.broadcast("profile.created", {"profile_id": profile.id})
    return await _profile_response(session, profile)


@router.get("/profiles/{profile_id}", response_model=ControlProfileResponse)
async def get_profile(profile_id: int, session: SessionDependency) -> ControlProfileResponse:
    return await _profile_response(session, await _get_profile(session, profile_id))


@router.patch("/profiles/{profile_id}", response_model=ControlProfileResponse)
async def update_profile(
    profile_id: int,
    payload: ControlProfileUpdate,
    session: SessionDependency,
) -> ControlProfileResponse:
    profile = await _get_profile(session, profile_id)
    values = payload.model_dump(exclude_unset=True)
    if "name" in values:
        duplicate = await session.scalar(
            select(ControlProfile.id).where(
                ControlProfile.source == active_source(),
                ControlProfile.id != profile.id,
                func.lower(ControlProfile.name) == values["name"].lower(),
            )
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A profile with this name already exists.",
            )
    for key, value in values.items():
        setattr(profile, key, value)
    await session.commit()
    await session.refresh(profile)
    await connection_manager.broadcast("profile.updated", {"profile_id": profile.id})
    return await _profile_response(session, profile)


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(profile_id: int, session: SessionDependency) -> Response:
    profile = await _get_profile(session, profile_id)
    rules = list(
        (
            await session.scalars(
                select(DomainRule).where(
                    DomainRule.source == active_source(),
                    DomainRule.scope_type == RuleScope.PROFILE.value,
                    DomainRule.scope_id == profile.id,
                )
            )
        ).all()
    )
    try:
        for rule in rules:
            await remove_domain_rule(rule)
    except ControlRuleRemovalError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    await session.execute(
        delete(DomainRule).where(
            DomainRule.source == active_source(),
            DomainRule.scope_type == RuleScope.PROFILE.value,
            DomainRule.scope_id == profile.id,
        )
    )
    await session.execute(
        update(Device)
        .where(Device.source == active_source(), Device.profile_id == profile.id)
        .values(profile_id=None)
    )
    await session.execute(
        update(InternetActivity)
        .where(InternetActivity.profile_id == profile.id)
        .values(profile_id=None)
    )
    await session.execute(delete(AccessSchedule).where(AccessSchedule.profile_id == profile.id))
    await session.delete(profile)
    await session.commit()
    await connection_manager.broadcast("profile.deleted", {"profile_id": profile_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/profiles/{profile_id}/devices", response_model=ControlProfileResponse)
async def assign_profile_devices(
    profile_id: int,
    payload: ProfileDeviceAssignment,
    session: SessionDependency,
) -> ControlProfileResponse:
    profile = await _get_profile(session, profile_id)
    requested = set(payload.device_ids)
    devices = list(
        (
            await session.scalars(
                select(Device).where(
                    Device.source == active_source(),
                    Device.network_cidr == settings.netwatch_subnet,
                    Device.network_id == settings.netwatch_network_id,
                    or_(Device.profile_id == profile.id, Device.id.in_(requested)),
                )
            )
        ).all()
    )
    found = {device.id for device in devices if device.id in requested}
    if found != requested:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more devices were not found.",
        )
    affected_profiles = {
        device.profile_id
        for device in devices
        if device.id in requested and device.profile_id not in {None, profile.id}
    }
    for device in devices:
        if device.id in requested:
            device.profile_id = profile.id
        elif device.profile_id == profile.id:
            device.profile_id = None
    await session.flush()
    await reconcile_profile_rules(session, profile.id, active_source())
    for affected_profile in affected_profiles:
        await reconcile_profile_rules(session, affected_profile, active_source())
    await session.commit()
    await session.refresh(profile)
    await connection_manager.broadcast("profile.devices_updated", {"profile_id": profile.id})
    return await _profile_response(session, profile)


@router.put("/profiles/{profile_id}/schedules", response_model=ControlProfileResponse)
async def replace_profile_schedules(
    profile_id: int,
    payload: ScheduleReplaceRequest,
    session: SessionDependency,
) -> ControlProfileResponse:
    profile = await _get_profile(session, profile_id)
    await session.execute(delete(AccessSchedule).where(AccessSchedule.profile_id == profile.id))
    session.add_all(
        AccessSchedule(profile_id=profile.id, **item.model_dump()) for item in payload.schedules
    )
    await session.commit()
    await session.refresh(profile)
    await connection_manager.broadcast("schedule.updated", {"profile_id": profile.id})
    return await _profile_response(session, profile)


@router.get("/domain-rules", response_model=list[DomainRuleResponse])
async def list_domain_rules(session: SessionDependency) -> list[DomainRuleResponse]:
    rules = list(
        (
            await session.scalars(
                select(DomainRule)
                .where(DomainRule.source == active_source())
                .order_by(DomainRule.created_at.desc())
            )
        ).all()
    )
    return [DomainRuleResponse.model_validate(rule) for rule in rules]


@router.post(
    "/domain-rules",
    response_model=DomainRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_domain_rule(
    payload: DomainRuleCreate, session: SessionDependency
) -> DomainRuleResponse:
    if payload.scope_type == RuleScope.PROFILE:
        await _get_profile(session, payload.scope_id or 0)
    elif payload.scope_type == RuleScope.DEVICE:
        device = await session.scalar(
            select(Device.id).where(
                Device.id == payload.scope_id,
                Device.source == active_source(),
                Device.network_cidr == settings.netwatch_subnet,
                Device.network_id == settings.netwatch_network_id,
            )
        )
        if device is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")
    duplicate = await session.scalar(
        select(DomainRule.id).where(
            DomainRule.source == active_source(),
            DomainRule.scope_type == payload.scope_type.value,
            DomainRule.scope_id.is_(None)
            if payload.scope_id is None
            else DomainRule.scope_id == payload.scope_id,
            DomainRule.domain == payload.domain,
            DomainRule.action == payload.action.value,
            DomainRule.enabled.is_(True),
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An equivalent active rule already exists.",
        )
    rule = DomainRule(
        source=active_source(),
        **payload.model_dump(mode="python"),
    )
    session.add(rule)
    await session.flush()
    await enforce_domain_rule(session, rule, active_source())
    await session.commit()
    await session.refresh(rule)
    await connection_manager.broadcast(
        "policy.rule_updated",
        {"rule_id": rule.id, "status": rule.enforcement_status},
    )
    return DomainRuleResponse.model_validate(rule)


@router.post("/domain-rules/{rule_id}/retry", response_model=DomainRuleResponse)
async def retry_domain_rule(rule_id: int, session: SessionDependency) -> DomainRuleResponse:
    rule = await session.scalar(
        select(DomainRule).where(DomainRule.id == rule_id, DomainRule.source == active_source())
    )
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found.")
    await enforce_domain_rule(session, rule, active_source())
    await session.commit()
    await session.refresh(rule)
    return DomainRuleResponse.model_validate(rule)


@router.delete("/domain-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain_rule(rule_id: int, session: SessionDependency) -> Response:
    rule = await session.scalar(
        select(DomainRule).where(DomainRule.id == rule_id, DomainRule.source == active_source())
    )
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found.")
    try:
        await remove_domain_rule(rule)
    except ControlRuleRemovalError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    await session.delete(rule)
    await session.commit()
    await connection_manager.broadcast("policy.rule_deleted", {"rule_id": rule_id})
    return Response(status_code=status.HTTP_204_NO_CONTENT)
