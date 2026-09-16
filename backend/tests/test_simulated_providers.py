from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from database.base import Base
from models.control import AccessAudit
from models.device import Device, DeviceSource, DeviceStatus
from services.control.actions import NetworkControlActionError, perform_network_action
from services.providers.network.base import NetworkCapability
from services.providers.registry import provider_registry
from services.simulation.providers import SimulatedNetworkControlProvider


@pytest.fixture
async def control_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    yield factory
    await test_engine.dispose()


@pytest.fixture(autouse=True)
def restore_registry():
    yield
    provider_registry.clear_simulation()


async def _seed_demo_device(
    factory: async_sessionmaker[AsyncSession], **overrides: object
) -> Device:
    now = datetime.now(UTC)
    async with factory() as session:
        device = Device(
            name="Simulated-TV",
            ip_address="192.168.1.60",
            mac_address="02:11:22:AA:10:40",
            hostname="simulated-tv.netwatch.sim",
            vendor="Samsung",
            status=DeviceStatus.ONLINE,
            source=DeviceSource.DEMO,
            network_cidr="192.168.1.0/24",
            network_id="legacy",
            latency_ms=9.0,
            first_seen=now,
            last_seen=now,
            device_type="tv",
            **overrides,  # type: ignore[arg-type]
        )
        session.add(device)
        await session.commit()
        await session.refresh(device)
        return device


async def test_simulated_router_declares_the_core_control_capabilities() -> None:
    provider = SimulatedNetworkControlProvider()

    for capability in (
        NetworkCapability.BLOCK_INTERNET,
        NetworkCapability.UNBLOCK_INTERNET,
        NetworkCapability.QUARANTINE_DEVICE,
        NetworkCapability.RELEASE_DEVICE,
        NetworkCapability.FIREWALL_RULES,
    ):
        provider.require(capability)

    health = await provider.test_connection()
    assert health.status.value == "connected"
    assert provider.provider_id == "simulated_router"


async def test_pause_and_resume_internet_are_applied_to_demo_devices(
    control_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider_registry.configure_simulation()
    device = await _seed_demo_device(control_session_factory)
    async with control_session_factory() as session:
        stored = await session.get(Device, device.id)
        assert stored is not None
        result = await perform_network_action(
            session, stored, "pause_internet", duration_minutes=30, actor="administrator"
        )
        await session.commit()

        assert result.changed is True
        assert stored.internet_access == "paused"
        assert stored.paused_until is not None
        assert stored.control_provider_id == "simulated_router"
        audits = list((await session.scalars(select(AccessAudit))).all())
        assert any(
            audit.action == "pause_internet" and audit.result == "completed" for audit in audits
        )

        resume = await perform_network_action(
            session, stored, "resume_internet", actor="administrator"
        )
        await session.commit()
        assert resume.changed is True
        assert stored.internet_access == "allowed"
        assert stored.control_identifier is None


async def test_block_device_applies_a_simulated_firewall_rule(
    control_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider_registry.configure_simulation()
    device = await _seed_demo_device(control_session_factory)
    async with control_session_factory() as session:
        stored = await session.get(Device, device.id)
        assert stored is not None
        result = await perform_network_action(
            session, stored, "block_device", actor="administrator"
        )
        await session.commit()

        assert result.changed is True
        assert stored.trust_state == "blocked"
        assert stored.internet_access == "blocked"
        assert stored.lan_access == "blocked"


async def test_the_simulated_gateway_stays_protected(
    control_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    provider_registry.configure_simulation()
    device = await _seed_demo_device(control_session_factory, is_gateway=True)
    async with control_session_factory() as session:
        stored = await session.get(Device, device.id)
        assert stored is not None
        with pytest.raises(NetworkControlActionError):
            await perform_network_action(session, stored, "pause_internet", actor="administrator")
        await session.commit()
        audits = list((await session.scalars(select(AccessAudit))).all())
        assert any(audit.result == "failed" for audit in audits)
        assert stored.internet_access == "allowed"
