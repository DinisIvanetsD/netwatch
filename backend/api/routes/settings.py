from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from database.session import get_session
from models.setting import AppSetting
from schemas.settings import HistoryClearResponse, SettingsResponse, SettingsUpdate
from services.monitoring.engine import monitoring_engine
from services.realtime.manager import connection_manager
from services.retention import clear_historical_data
from services.scanner.coordinator import scan_coordinator

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
        retention_days=settings.retention_days,
    )


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    return current_settings()


@router.patch("", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdate, session: SessionDependency) -> SettingsResponse:
    scanner_keys = {
        "subnet",
        "scan_interval",
        "scan_concurrency",
        "offline_after_missed_scans",
    }
    if scan_coordinator.running and payload.model_fields_set.intersection(scanner_keys):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scanner settings cannot change while a scan is running.",
        )

    setting_names = {
        "subnet": "netwatch_subnet",
        "scan_interval": "scan_interval",
        "scan_concurrency": "scan_concurrency",
        "monitoring_enabled": "monitoring_enabled",
        "offline_after_missed_scans": "offline_after_missed_scans",
        "retention_days": "retention_days",
    }
    for payload_name, setting_name in setting_names.items():
        value = getattr(payload, payload_name)
        if value is not None:
            setattr(settings, setting_name, value)
            await session.merge(AppSetting(key=setting_name, value=value))
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
    if payload.monitoring_enabled is False:
        await monitoring_engine.stop()
    elif payload.monitoring_enabled is True:
        monitoring_engine.start()
    await connection_manager.broadcast("settings.updated", {})
    return current_settings()


@router.delete("/history", response_model=HistoryClearResponse)
async def clear_history(session: SessionDependency) -> HistoryClearResponse:
    if scan_coordinator.running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Historical data cannot be cleared while a scan is running.",
        )
    result = await clear_historical_data(session)
    await session.commit()
    await connection_manager.broadcast("history.cleared", {})
    return HistoryClearResponse(**asdict(result))
