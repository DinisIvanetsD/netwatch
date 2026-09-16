from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from database.session import get_session
from models.device import Device, DeviceSource
from models.setting import AppSetting
from schemas.settings import HistoryClearResponse, SettingsResponse, SettingsUpdate
from services.demo import (
    seed_demo_alerts,
    seed_demo_devices,
    seed_demo_history,
    seed_demo_internet_activity,
    seed_demo_services,
)
from services.integrations import load_provider_integrations
from services.monitoring.engine import monitoring_engine
from services.network_identity import manual_network_id
from services.network_transition import transition_network
from services.providers.registry import provider_registry
from services.realtime.manager import connection_manager
from services.retention import clear_historical_data
from services.scanner.coordinator import scan_coordinator
from services.simulation import simulation_engine
from services.simulation.engine import operating_mode

router = APIRouter(prefix="/settings", tags=["settings"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def current_settings() -> SettingsResponse:
    return SettingsResponse(
        subnet=settings.netwatch_subnet,
        auto_detect_network=settings.auto_detect_network,
        scan_interval=settings.scan_interval,
        scan_concurrency=settings.scan_concurrency,
        monitoring_enabled=settings.monitoring_enabled,
        service_scan_enabled=settings.service_scan_enabled,
        service_ports=list(settings.approved_service_ports),
        offline_after_missed_scans=settings.offline_after_missed_scans,
        new_device_alerts=settings.new_device_alerts,
        new_device_policy=settings.new_device_policy,
        device_offline_alerts=settings.device_offline_alerts,
        new_service_alerts=settings.new_service_alerts,
        latency_alerts=settings.latency_alerts,
        retention_days=settings.retention_days,
        operating_mode=operating_mode(),
    )


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    return current_settings()


@router.patch("", response_model=SettingsResponse)
async def update_settings(payload: SettingsUpdate, session: SessionDependency) -> SettingsResponse:
    scanner_keys = {
        "subnet",
        "auto_detect_network",
        "operating_mode",
        "scan_interval",
        "scan_concurrency",
        "offline_after_missed_scans",
    }
    if scan_coordinator.running and payload.model_fields_set.intersection(scanner_keys):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scanner settings cannot change while a scan is running.",
        )

    if payload.subnet is not None and payload.subnet != settings.netwatch_subnet:
        await transition_network(
            session,
            subnet=payload.subnet,
            network_id=manual_network_id(payload.subnet),
            source=DeviceSource.DEMO if settings.netwatch_demo_mode else DeviceSource.LIVE,
            actor="administrator",
        )

    setting_names = {
        "subnet": "netwatch_subnet",
        "auto_detect_network": "auto_detect_network",
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
        "new_device_policy",
    ):
        value = getattr(payload, key)
        if value is not None:
            setattr(settings, key, value)
            await session.merge(AppSetting(key=key, value=value))
    mode_changed = False
    simulation_requested = False
    if payload.operating_mode is not None:
        simulation_requested = payload.operating_mode == "simulation"
        mode_changed = simulation_requested != settings.netwatch_demo_mode
        if mode_changed:
            # Flip the flag before seeding so the demo seeds accept the request.
            settings.netwatch_demo_mode = simulation_requested
            await session.merge(AppSetting(key="netwatch_demo_mode", value=simulation_requested))
            if simulation_requested:
                # Re-home the simulated inventory into the currently active network
                # scope so demo data stays visible next to whichever live scope was
                # in use before the switch.
                await session.execute(
                    update(Device)
                    .where(Device.source == DeviceSource.DEMO)
                    .values(
                        network_cidr=settings.netwatch_subnet,
                        network_id=settings.netwatch_network_id,
                    )
                    .execution_options(synchronize_session=False)
                )
    await session.commit()
    if mode_changed:
        if simulation_requested:
            await seed_demo_devices()
            await seed_demo_history()
            await seed_demo_services()
            await seed_demo_internet_activity()
            await seed_demo_alerts()
            provider_registry.configure_simulation()
            simulation_engine.start()
        else:
            await simulation_engine.stop()
            provider_registry.clear_simulation()
            await load_provider_integrations()
        await connection_manager.broadcast(
            "mode.changed", {"operating_mode": payload.operating_mode}
        )
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
