from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core.config import settings
from database.base import Base
from database.session import get_session
from main import app
from models.alert import Alert
from models.device import Device, DeviceSource, DeviceStatus
from models.event import Event, EventSeverity, EventType
from models.metric import DeviceMetric
from models.scan import Scan, ScanStatus
from models.service import Service
from services.retention import prune_expired_history


@pytest.fixture
async def device_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    yield factory
    await test_engine.dispose()


@pytest.fixture
async def device_client(
    device_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[TestClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with device_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def live_device(device_session_factory: async_sessionmaker[AsyncSession]) -> Device:
    now = datetime.now(UTC)
    async with device_session_factory() as session:
        device = Device(
            name="Test Router",
            ip_address="192.168.1.1",
            mac_address="AA:BB:CC:DD:EE:01",
            hostname="router.test",
            vendor="Test Vendor",
            status=DeviceStatus.ONLINE,
            source=DeviceSource.LIVE,
            latency_ms=1.5,
            first_seen=now,
            last_seen=now,
            is_gateway=True,
        )
        session.add(device)
        await session.commit()
        await session.refresh(device)
        return device


async def test_list_devices_returns_paginated_inventory(
    device_client: TestClient,
    live_device: Device,
) -> None:
    response = device_client.get("/api/devices")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == live_device.id
    assert body["items"][0]["status"] == "online"
    assert body["items"][0]["last_seen"].endswith("Z")


async def test_device_detail_returns_404_for_unknown_device(device_client: TestClient) -> None:
    response = device_client.get("/api/devices/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "Device not found."}


async def test_device_history_and_event_endpoints(
    device_client: TestClient,
    device_session_factory: async_sessionmaker[AsyncSession],
    live_device: Device,
) -> None:
    now = datetime.now(UTC)
    async with device_session_factory() as session:
        session.add(
            DeviceMetric(
                device_id=live_device.id,
                timestamp=now,
                latency_ms=2.5,
                online=True,
            )
        )
        session.add(
            Event(
                device_id=live_device.id,
                type=EventType.DEVICE_ONLINE,
                message="Test Router came back online.",
                severity=EventSeverity.INFO,
                timestamp=now,
                metadata_payload={},
                source=DeviceSource.LIVE,
            )
        )
        await session.commit()

    metrics = device_client.get(f"/api/devices/{live_device.id}/metrics")
    events = device_client.get(f"/api/devices/{live_device.id}/events")
    activity = device_client.get("/api/events?severity=info")

    assert metrics.status_code == 200
    assert metrics.json()["items"][0]["latency_ms"] == 2.5
    assert events.status_code == 200
    assert events.json()["items"][0]["type"] == "device.online"
    assert activity.status_code == 200
    assert activity.json()["items"][0]["device_name"] == "Test Router"


async def test_service_endpoints_return_observed_ports(
    device_client: TestClient,
    device_session_factory: async_sessionmaker[AsyncSession],
    live_device: Device,
) -> None:
    now = datetime.now(UTC)
    async with device_session_factory() as session:
        session.add(
            Service(
                device_id=live_device.id,
                port=443,
                protocol="tcp",
                service_name="HTTPS",
                first_seen=now,
                last_seen=now,
                active=True,
            )
        )
        await session.commit()

    aggregate = device_client.get("/api/services")
    detail = device_client.get(f"/api/services/device/{live_device.id}")
    inventory = device_client.get("/api/devices")

    assert aggregate.status_code == 200
    assert aggregate.json()["items"][0]["service_name"] == "HTTPS"
    assert detail.status_code == 200
    assert detail.json()["items"][0]["port"] == 443
    assert inventory.json()["items"][0]["service_ports"] == [443]


async def test_network_status_and_activity_use_persisted_data(
    device_client: TestClient,
    device_session_factory: async_sessionmaker[AsyncSession],
    live_device: Device,
) -> None:
    now = datetime.now(UTC)
    async with device_session_factory() as session:
        session.add_all(
            [
                DeviceMetric(
                    device_id=live_device.id,
                    timestamp=now,
                    latency_ms=3.0,
                    online=True,
                ),
                Event(
                    device_id=live_device.id,
                    type=EventType.DEVICE_ONLINE,
                    message="Test Router came online.",
                    severity=EventSeverity.INFO,
                    timestamp=now,
                    metadata_payload={},
                    source=DeviceSource.LIVE,
                ),
                Scan(
                    started_at=now,
                    finished_at=now,
                    status=ScanStatus.COMPLETED,
                    devices_found=1,
                    duration_ms=25,
                    subnet="192.168.1.0/24",
                    source=DeviceSource.LIVE,
                ),
            ]
        )
        await session.commit()

    status = device_client.get("/api/network/status")
    activity = device_client.get("/api/network/activity?hours=1")

    assert status.status_code == 200
    assert status.json()["gateway"] == "192.168.1.1"
    assert status.json()["online_devices"] == 1
    assert status.json()["average_latency_ms"] == 1.5
    assert status.json()["last_completed_scan"] is not None
    assert activity.status_code == 200
    assert activity.json()["hours"] == 1
    assert activity.json()["points"][0]["online_devices"] == 1
    assert activity.json()["points"][0]["average_latency_ms"] == 3.0
    assert activity.json()["points"][0]["events"] == 1


async def test_alert_can_be_created_read_and_resolved(
    device_client: TestClient,
    device_session_factory: async_sessionmaker[AsyncSession],
    live_device: Device,
) -> None:
    now = datetime.now(UTC)
    async with device_session_factory() as session:
        alert = Alert(
            device_id=live_device.id,
            type="device.offline",
            severity=EventSeverity.MEDIUM,
            title="Device offline",
            description="Test Router went offline.",
            created_at=now,
            read=False,
            resolved=False,
            source=DeviceSource.LIVE,
        )
        session.add(alert)
        await session.commit()
        await session.refresh(alert)
        alert_id = alert.id

    listing = device_client.get("/api/alerts?unresolved_only=true")
    update = device_client.patch(f"/api/alerts/{alert_id}", json={"read": True, "resolved": True})
    assert listing.status_code == 200
    assert listing.json()["items"][0]["title"] == "Device offline"
    assert update.status_code == 200
    assert update.json()["read"] is True
    assert update.json()["resolved"] is True
    assert update.json()["resolved_at"] is not None


async def test_scanner_and_retention_settings_can_be_updated(
    device_client: TestClient,
) -> None:
    original = {
        "netwatch_subnet": settings.netwatch_subnet,
        "scan_interval": settings.scan_interval,
        "scan_concurrency": settings.scan_concurrency,
        "monitoring_enabled": settings.monitoring_enabled,
        "offline_after_missed_scans": settings.offline_after_missed_scans,
        "retention_days": settings.retention_days,
    }
    try:
        response = device_client.patch(
            "/api/settings",
            json={
                "subnet": "10.42.0.0/24",
                "scan_interval": 120,
                "scan_concurrency": 16,
                "monitoring_enabled": False,
                "offline_after_missed_scans": 2,
                "retention_days": 90,
            },
        )
        invalid = device_client.patch("/api/settings", json={"subnet": "8.8.8.0/24"})

        assert response.status_code == 200
        assert response.json()["subnet"] == "10.42.0.0/24"
        assert response.json()["scan_interval"] == 120
        assert response.json()["monitoring_enabled"] is False
        assert response.json()["retention_days"] == 90
        assert invalid.status_code == 422
    finally:
        for key, value in original.items():
            setattr(settings, key, value)


async def test_clear_history_preserves_inventory_and_services(
    device_client: TestClient,
    device_session_factory: async_sessionmaker[AsyncSession],
    live_device: Device,
) -> None:
    now = datetime.now(UTC)
    async with device_session_factory() as session:
        event = Event(
            device_id=live_device.id,
            type=EventType.DEVICE_ONLINE,
            message="Test Router came online.",
            severity=EventSeverity.INFO,
            timestamp=now,
            metadata_payload={},
            source=DeviceSource.LIVE,
        )
        session.add(event)
        await session.flush()
        session.add_all(
            [
                DeviceMetric(
                    device_id=live_device.id,
                    timestamp=now,
                    latency_ms=1.5,
                    online=True,
                ),
                Service(
                    device_id=live_device.id,
                    port=443,
                    protocol="tcp",
                    service_name="HTTPS",
                    first_seen=now,
                    last_seen=now,
                    active=True,
                ),
                Alert(
                    device_id=live_device.id,
                    event_id=event.id,
                    type="device.online",
                    severity=EventSeverity.INFO,
                    title="Device online",
                    description="Test Router came online.",
                    created_at=now,
                    read=False,
                    resolved=False,
                    source=DeviceSource.LIVE,
                ),
                Scan(
                    started_at=now,
                    finished_at=now,
                    status=ScanStatus.COMPLETED,
                    devices_found=1,
                    duration_ms=20,
                    subnet="192.168.1.0/24",
                    source=DeviceSource.LIVE,
                ),
            ]
        )
        await session.commit()

    cleared = device_client.delete("/api/settings/history")

    assert cleared.status_code == 200
    assert cleared.json() == {
        "metrics_deleted": 1,
        "events_deleted": 1,
        "alerts_deleted": 1,
        "scans_deleted": 1,
        "internet_activity_deleted": 0,
    }
    assert device_client.get("/api/devices").json()["total"] == 1
    assert device_client.get("/api/services").json()["total"] == 1


async def test_retention_pruning_handles_sqlite_loaded_datetimes(
    device_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    now = datetime.now(UTC)
    async with device_session_factory() as session:
        old_scan = Scan(
            started_at=now - timedelta(days=40),
            finished_at=now - timedelta(days=40),
            status=ScanStatus.COMPLETED,
            devices_found=0,
            duration_ms=10,
            subnet="192.168.1.0/24",
            source=DeviceSource.LIVE,
            created_at=now - timedelta(days=40),
        )
        current_scan = Scan(
            started_at=now,
            status=ScanStatus.RUNNING,
            devices_found=0,
            subnet="192.168.1.0/24",
            source=DeviceSource.LIVE,
            created_at=now,
        )
        session.add_all([old_scan, current_scan])
        await session.commit()
        current_scan_id = current_scan.id
        session.expire_all()

        loaded_current_scan = await session.get(Scan, current_scan_id)
        assert loaded_current_scan is not None
        result = await prune_expired_history(session, retention_days=30)
        await session.commit()

        assert result.scans_deleted == 1
        assert await session.get(Scan, current_scan_id) is not None
