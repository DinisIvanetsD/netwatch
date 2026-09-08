from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from database.session import get_session
from models.setting import AppSetting
from schemas.settings import SettingsResponse, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def current_settings() -> SettingsResponse:
    return SettingsResponse(
        subnet=settings.netwatch_subnet,
        scan_interval=settings.scan_interval,
        scan_concurrency=settings.scan_concurrency,
        monitoring_enabled=settings.monitoring_enabled,
        service_scan_enabled=settings.service_scan_enabled,
        service_ports=list(settings.approved_service_ports),
        offline_after_missed_scans=settings.offline_after_missed_scans,
        new_device_alerts=settings.new_device_alerts,
        device_offline_alerts=settings.device_offline_alerts,
        new_service_alerts=settings.new_service_alerts,
        latency_alerts=settings.latency_alerts,
    )


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    return current_settings()


@router.patch("", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdate, session: SessionDependency) -> SettingsResponse:
    if payload.service_scan_enabled is not None:
        settings.service_scan_enabled = payload.service_scan_enabled
        await session.merge(
            AppSetting(key="service_scan_enabled", value=payload.service_scan_enabled)
        )
    if payload.service_ports is not None:
        settings.service_ports = ",".join(str(port) for port in payload.service_ports)
        await session.merge(AppSetting(key="service_ports", value=payload.service_ports))
    for key in (
        "new_device_alerts",
        "device_offline_alerts",
        "new_service_alerts",
        "latency_alerts",
    ):
        value = getattr(payload, key)
        if value is not None:
            setattr(settings, key, value)
            await session.merge(AppSetting(key=key, value=value))
    await session.commit()
    return current_settings()
