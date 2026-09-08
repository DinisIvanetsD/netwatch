from datetime import UTC, datetime, timedelta
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_session
from models.internet_activity import InternetActivity
from schemas.internet_activity import (
    InternetActivityListResponse,
    InternetActivityResponse,
    InternetActivitySummaryResponse,
)

router = APIRouter(prefix="/internet-activity", tags=["internet activity"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


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
    filters = [InternetActivity.timestamp >= datetime.now(UTC) - timedelta(hours=hours)]
    if device_id is not None:
        filters.append(InternetActivity.device_id == device_id)
    if category:
        filters.append(InternetActivity.category == category)
    if blocked is not None:
        filters.append(InternetActivity.blocked.is_(blocked))
    if search:
        filters.append(InternetActivity.domain.ilike(f"%{search}%"))
    items = list(
        (
            await session.scalars(
                select(InternetActivity)
                .where(*filters)
                .order_by(InternetActivity.timestamp.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        ).all()
    )
    total = int(
        (await session.scalar(select(func.count()).select_from(InternetActivity).where(*filters)))
        or 0
    )
    return InternetActivityListResponse(
        items=[InternetActivityResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        per_page=per_page,
        pages=ceil(total / per_page) if total else 0,
    )


@router.get("/summary", response_model=InternetActivitySummaryResponse)
async def internet_activity_summary(
    session: SessionDependency,
    hours: Annotated[int, Query(ge=1, le=24 * 90)] = 24,
) -> InternetActivitySummaryResponse:
    since = datetime.now(UTC) - timedelta(hours=hours)
    base = InternetActivity.timestamp >= since
    total = int((await session.scalar(select(func.count()).where(base))) or 0)
    blocked = int(
        (await session.scalar(select(func.count()).where(base, InternetActivity.blocked.is_(True))))
        or 0
    )
    active_devices = int(
        (
            await session.scalar(
                select(func.count(func.distinct(InternetActivity.device_id))).where(base)
            )
        )
        or 0
    )
    top_domains = (
        await session.execute(
            select(InternetActivity.domain, func.count().label("count"))
            .where(base)
            .group_by(InternetActivity.domain)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()
    categories = (
        await session.execute(
            select(InternetActivity.category, func.count().label("count"))
            .where(base)
            .group_by(InternetActivity.category)
            .order_by(func.count().desc())
        )
    ).all()
    return InternetActivitySummaryResponse(
        total_queries=total,
        blocked_queries=blocked,
        active_devices=active_devices,
        top_domains=[{"domain": domain, "count": count} for domain, count in top_domains],
        categories=[{"category": category, "count": count} for category, count in categories],
    )
