from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core.config import settings
from database.base import Base
from models.alert import Alert
from models.device import Device, DeviceSource, DeviceStatus
from models.event import EventSeverity, EventType
from models.metric import DeviceMetric
from services.simulation.engine import SimulationEngine


@pytest.fixture
async def simulation_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    yield factory
    await test_engine.dispose()


async def _seed_simulated_device(
    factory: async_sessionmaker[AsyncSession],
    *,
    status: DeviceStatus = DeviceStatus.ONLINE,
    latency_ms: float | None = 10.0,
    mac_address: str = "02:11:22:AA:10:30",
    ip_address: str = "192.168.1.50",
    source: DeviceSource = DeviceSource.DEMO,
) -> Device:
    now = datetime.now(UTC)
    async with factory() as session:
        device = Device(
            name="Simulated-TV",
            ip_address=ip_address,
            mac_address=mac_address,
            hostname="simulated-tv.netwatch.sim",
            vendor="Samsung",
            status=status,
            source=source,
            network_cidr=settings.netwatch_subnet,
            network_id=settings.netwatch_network_id,
            latency_ms=latency_ms,
            first_seen=now,
            last_seen=now,
        )
        session.add(device)
        await session.commit()
        await session.refresh(device)
        return device


async def test_tick_records_metrics_for_every_simulated_device(
    simulation_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    device = await _seed_simulated_device(simulation_session_factory)
    engine = SimulationEngine(seed=11, session_factory=simulation_session_factory)

    outcome = await engine.tick()

    assert outcome.devices == 1
    assert outcome.online_devices == 1
    async with simulation_session_factory() as session:
        metrics = list((await session.scalars(select(DeviceMetric))).all())
        assert len(metrics) == 1
        assert metrics[0].device_id == device.id
        assert metrics[0].online is True
        assert metrics[0].latency_ms is not None


async def test_tick_can_take_a_device_offline_and_raise_an_alert(
    simulation_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device = await _seed_simulated_device(simulation_session_factory)
    monkeypatch.setattr("services.simulation.engine.OFFLINE_CHANCE", 1.0)
    monkeypatch.setattr("services.simulation.engine.ARRIVAL_CHANCE", 0.0)
    engine = SimulationEngine(seed=3, session_factory=simulation_session_factory)

    outcome = await engine.tick()

    assert outcome.online_devices == 0
    assert [event.type for event in outcome.events] == [EventType.DEVICE_OFFLINE]
    assert outcome.events[0].severity == EventSeverity.MEDIUM
    assert [alert.type for alert in outcome.alerts] == [EventType.DEVICE_OFFLINE.value]
    async with simulation_session_factory() as session:
        stored = await session.get(Device, device.id)
        assert stored is not None
        assert stored.status == DeviceStatus.OFFLINE
        alerts = list((await session.scalars(select(Alert))).all())
        assert len(alerts) == 1
        assert alerts[0].resolved is False


async def test_offline_device_recovers_and_resolves_its_alert(
    simulation_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device = await _seed_simulated_device(
        simulation_session_factory, status=DeviceStatus.OFFLINE, latency_ms=None
    )
    async with simulation_session_factory() as session:
        session.add(
            Alert(
                device_id=device.id,
                type=EventType.DEVICE_OFFLINE.value,
                severity=EventSeverity.MEDIUM,
                title="Device offline",
                description="Simulated-TV went offline on the simulated network.",
                created_at=datetime.now(UTC),
                source=DeviceSource.DEMO,
                resolved=False,
            )
        )
        await session.commit()
    monkeypatch.setattr("services.simulation.engine.RECOVERY_CHANCE", 1.0)
    monkeypatch.setattr("services.simulation.engine.ARRIVAL_CHANCE", 0.0)
    engine = SimulationEngine(seed=5, session_factory=simulation_session_factory)

    outcome = await engine.tick()

    assert [event.type for event in outcome.events] == [EventType.DEVICE_ONLINE]
    async with simulation_session_factory() as session:
        stored = await session.get(Device, device.id)
        assert stored is not None
        assert stored.status == DeviceStatus.ONLINE
        alerts = list((await session.scalars(select(Alert))).all())
        assert len(alerts) == 1
        assert alerts[0].resolved is True


async def test_tick_can_add_a_new_simulated_device(
    simulation_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_simulated_device(simulation_session_factory)
    monkeypatch.setattr("services.simulation.engine.ARRIVAL_CHANCE", 1.0)
    engine = SimulationEngine(seed=7, session_factory=simulation_session_factory)

    outcome = await engine.tick()

    assert len(outcome.created) == 1
    assert outcome.devices == 2
    arrival = outcome.created[0]
    assert arrival.source == DeviceSource.DEMO
    assert arrival.network_cidr == settings.netwatch_subnet
    assert arrival.ip_address != "192.168.1.50"
    assert EventType.DEVICE_DISCOVERED in {event.type for event in outcome.events}
    async with simulation_session_factory() as session:
        count = len(list((await session.scalars(select(Device))).all()))
        assert count == 2


async def test_tick_never_touches_live_inventory(
    simulation_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device = await _seed_simulated_device(
        simulation_session_factory, source=DeviceSource.LIVE, mac_address="02:11:22:AA:10:99"
    )
    monkeypatch.setattr("services.simulation.engine.ARRIVAL_CHANCE", 0.0)
    engine = SimulationEngine(seed=13, session_factory=simulation_session_factory)

    outcome = await engine.tick()

    assert outcome.devices == 0
    async with simulation_session_factory() as session:
        metrics = list((await session.scalars(select(DeviceMetric))).all())
        assert metrics == []
        stored = await session.get(Device, device.id)
        assert stored is not None
        assert stored.source == DeviceSource.LIVE
