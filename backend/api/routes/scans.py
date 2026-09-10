from datetime import UTC, datetime
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from database.session import get_session
from models.device import DeviceSource
from models.scan import Scan, ScanStatus
from schemas.scan import ScanListResponse, ScanResponse
from services.network_identity import scan_in_current_network
from services.scanner.coordinator import scan_coordinator
from services.scanner.service import scan_service

router = APIRouter(prefix="/scans", tags=["scans"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def active_source() -> DeviceSource:
    return DeviceSource.DEMO if settings.netwatch_demo_mode else DeviceSource.LIVE


@router.post("", response_model=ScanResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_scan(session: SessionDependency) -> ScanResponse:
    if not await scan_coordinator.reserve():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A scan is already running."
        )

    try:
        scan = Scan(
            status=ScanStatus.PENDING,
            subnet=settings.netwatch_subnet,
            network_id=settings.netwatch_network_id,
            source=active_source(),
            created_at=datetime.now(UTC),
        )
        session.add(scan)
        await session.commit()
        await session.refresh(scan)
    except Exception:
        await scan_coordinator.release()
        raise

    scan_coordinator.schedule(scan_service.run(scan.id))
    return ScanResponse.model_validate(scan)


@router.get("", response_model=ScanListResponse)
async def list_scans(
    session: SessionDependency,
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ScanListResponse:
    filters = [
        Scan.source == active_source(),
        scan_in_current_network(),
    ]
    items = list(
        (
            await session.scalars(
                select(Scan)
                .where(*filters)
                .order_by(Scan.created_at.desc(), Scan.id.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        ).all()
    )
    total = int((await session.scalar(select(func.count()).select_from(Scan).where(*filters))) or 0)
    return ScanListResponse(
        items=[ScanResponse.model_validate(scan) for scan in items],
        page=page,
        per_page=per_page,
        total=total,
        pages=ceil(total / per_page) if total else 0,
    )


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(scan_id: int, session: SessionDependency) -> ScanResponse:
    scan = await session.scalar(
        select(Scan).where(
            Scan.id == scan_id,
            Scan.source == active_source(),
            scan_in_current_network(),
        )
    )
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")
    return ScanResponse.model_validate(scan)
