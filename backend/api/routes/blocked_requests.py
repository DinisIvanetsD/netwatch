from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import active_source
from database.session import get_session
from models.control import ControlProfile, DomainRule
from models.device import Device
from models.internet_activity import InternetActivity
from schemas.control import BlockedRequestListResponse, BlockedRequestResponse
from services.control.constants import CATEGORY_LABELS

router = APIRouter(prefix="/blocked-requests", tags=["blocked requests"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]

REASON_LABELS = {
    "FilteredBlackList": "DNS block rule or filter list",
    "FilteredSafeBrowsing": "Safe Browsing protection",
    "FilteredParental": "Parental protection",
    "FilteredInvalid": "Invalid or disallowed DNS request",
    "FilteredBlockedService": "Blocked service policy",
}


def _domain_matches(rule: DomainRule, domain: str) -> bool:
    return domain == rule.domain or (rule.include_subdomains and domain.endswith(f".{rule.domain}"))


def _matching_rule(
    rules: list[DomainRule],
    *,
    domain: str,
    device_id: int,
    profile_id: int | None,
) -> DomainRule | None:
    candidates = [
        rule
        for rule in rules
        if rule.action == "block"
        and _domain_matches(rule, domain)
        and (
            rule.scope_type == "global"
            or (rule.scope_type == "device" and rule.scope_id == device_id)
            or (rule.scope_type == "profile" and rule.scope_id == profile_id)
        )
    ]
    rank = {"global": 1, "profile": 2, "device": 3}
    return max(candidates, key=lambda item: rank[item.scope_type], default=None)


@router.get("", response_model=BlockedRequestListResponse)
async def list_blocked_requests(
    session: SessionDependency,
    device_id: int | None = None,
    profile_id: int | None = None,
    category: Annotated[str | None, Query(min_length=1, max_length=40)] = None,
    domain: Annotated[str | None, Query(min_length=1, max_length=253)] = None,
    hours: Annotated[int, Query(ge=1, le=24 * 365)] = 24 * 7,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=200)] = 50,
) -> BlockedRequestListResponse:
    effective_profile = func.coalesce(InternetActivity.profile_id, Device.profile_id)
    filters = [
        Device.source == active_source(),
        InternetActivity.blocked.is_(True),
        InternetActivity.timestamp >= datetime.now(UTC) - timedelta(hours=hours),
    ]
    if device_id is not None:
        filters.append(InternetActivity.device_id == device_id)
    if profile_id is not None:
        filters.append(effective_profile == profile_id)
    if category:
        filters.append(InternetActivity.category == category)
    if domain:
        filters.append(InternetActivity.domain.ilike(f"%{domain.strip()}%"))

    rows = (
        await session.execute(
            select(
                InternetActivity,
                func.coalesce(Device.name, Device.hostname, Device.ip_address),
                Device.profile_id,
                ControlProfile.name,
            )
            .join(Device, Device.id == InternetActivity.device_id)
            .outerjoin(ControlProfile, ControlProfile.id == effective_profile)
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
    now = datetime.now(UTC)
    rules = list(
        (
            await session.scalars(
                select(DomainRule).where(
                    DomainRule.source == active_source(),
                    DomainRule.enabled.is_(True),
                )
            )
        ).all()
    )
    active_rules = [
        rule
        for rule in rules
        if rule.expires_at is None
        or (rule.expires_at if rule.expires_at.tzinfo else rule.expires_at.replace(tzinfo=UTC))
        > now
    ]
    items: list[BlockedRequestResponse] = []
    for activity, device_name, current_profile_id, profile_name in rows:
        observed_profile_id = activity.profile_id or current_profile_id
        matched = _matching_rule(
            active_rules,
            domain=activity.domain,
            device_id=activity.device_id,
            profile_id=observed_profile_id,
        )
        if matched:
            scope_label = {
                "global": "Global policy",
                "profile": profile_name or "Assigned profile",
                "device": device_name,
            }[matched.scope_type]
            rule_label = matched.reason or f"{scope_label} domain rule"
            explanation = (
                f"Blocked because the {scope_label} rule for {matched.domain} matched. "
                f"Enforcement source: {activity.provider_id}."
            )
        else:
            rule_label = REASON_LABELS.get(activity.reason or "", "DNS provider filtering policy")
            explanation = (
                f"Reported as blocked by {activity.provider_id}. Provider reason: "
                f"{activity.reason or 'not supplied'}."
            )
        items.append(
            BlockedRequestResponse(
                id=activity.id,
                device_id=activity.device_id,
                device_name=device_name,
                profile_id=observed_profile_id,
                profile_name=profile_name,
                timestamp=activity.timestamp,
                domain=activity.domain,
                registered_domain=activity.registered_domain,
                service=activity.service,
                category=CATEGORY_LABELS.get(activity.category, activity.category),
                rule=rule_label,
                provider_id=activity.provider_id,
                explanation=explanation,
            )
        )
    return BlockedRequestListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        pages=ceil(total / per_page) if total else 0,
    )
