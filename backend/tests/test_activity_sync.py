from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core.config import settings
from database.base import Base
from models.device import Device, DeviceSource, DeviceStatus
from models.device_address import DeviceAddressHistory
from models.internet_activity import InternetActivity
from services.activity import sync as sync_module
from services.providers.dns import DNSCapability, DNSQueryRecord


class FakeDNSProvider:
    provider_id = "test-dns"

    def __init__(self, records: list[DNSQueryRecord]) -> None:
        self.records = records

    def supports(self, capability: DNSCapability) -> bool:
        return capability == DNSCapability.QUERY_HISTORY

    async def query_history(self, *, limit: int = 100) -> list[DNSQueryRecord]:
        return self.records[:limit]


@pytest.fixture
async def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    import models  # noqa: F401  # Register all foreign-key targets before create_all.

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _device(ip: str, first_seen: datetime, last_seen: datetime) -> Device:
    return Device(
        ip_address=ip,
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        network_id=settings.netwatch_network_id,
        first_seen=first_seen,
        last_seen=last_seen,
        is_gateway=False,
    )


async def _run_sync(
    monkeypatch: pytest.MonkeyPatch,
    factory: async_sessionmaker[AsyncSession],
    records: list[DNSQueryRecord],
) -> int:
    provider = FakeDNSProvider(records)
    monkeypatch.setattr(sync_module.provider_registry, "dns", provider)
    monkeypatch.setattr(sync_module, "SessionLocal", factory)
    monkeypatch.setattr(
        sync_module.connection_manager,
        "broadcast",
        lambda *args, **kwargs: _completed(),
    )
    return await sync_module.sync_dns_activity()


async def _completed() -> None:
    return None


@pytest.mark.asyncio
async def test_sync_attributes_turnover_and_skips_overlap(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    turnover = start + timedelta(hours=1)
    records = [
        DNSQueryRecord(
            start + timedelta(minutes=30), "192.168.1.10", "old.test", "A", "NOERROR", False
        ),
        DNSQueryRecord(
            turnover + timedelta(minutes=30),
            "192.168.1.10",
            "new.test",
            "A",
            "NOERROR",
            False,
        ),
    ]
    async with session_factory() as session:
        old = _device("192.168.1.10", start, turnover)
        new = _device("192.168.1.10", turnover, turnover + timedelta(hours=1))
        session.add_all([old, new])
        await session.flush()
        session.add_all(
            [
                DeviceAddressHistory(
                    device_id=old.id,
                    ip_address=old.ip_address,
                    network_cidr=old.network_cidr,
                    network_id=old.network_id,
                    started_at=start,
                    ended_at=turnover,
                ),
                DeviceAddressHistory(
                    device_id=new.id,
                    ip_address=new.ip_address,
                    network_cidr=new.network_cidr,
                    network_id=new.network_id,
                    started_at=turnover,
                ),
            ]
        )
        await session.commit()

    assert await _run_sync(monkeypatch, session_factory, records) == 2
    async with session_factory() as session:
        activities = list((await session.scalars(select(InternetActivity))).all())
        devices = list((await session.scalars(select(Device).order_by(Device.id))).all())
        assert {activity.domain: activity.device_id for activity in activities} == {
            "old.test": devices[0].id,
            "new.test": devices[1].id,
        }

    overlap_record = DNSQueryRecord(
        turnover, "192.168.1.10", "ambiguous.test", "A", "NOERROR", False
    )
    assert await _run_sync(monkeypatch, session_factory, [overlap_record]) == 0


@pytest.mark.asyncio
async def test_sync_is_idempotent_across_device_resolution(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    timestamp = datetime(2026, 1, 1, 12, tzinfo=UTC)
    record = DNSQueryRecord(
        timestamp, "192.168.1.20", "same.test", "AAAA", "NOERROR", False
    )
    async with session_factory() as session:
        device = _device("192.168.1.20", timestamp - timedelta(hours=1), timestamp)
        session.add(device)
        await session.flush()
        session.add(
            DeviceAddressHistory(
                device_id=device.id,
                ip_address=device.ip_address,
                network_cidr=device.network_cidr,
                network_id=device.network_id,
                started_at=device.first_seen,
            )
        )
        await session.commit()

    assert await _run_sync(monkeypatch, session_factory, [record]) == 1

    async with session_factory() as session:
        old_device = (
            await session.scalars(select(Device).where(Device.ip_address == "192.168.1.20"))
        ).first()
        assert old_device is not None
        old_device.last_seen = timestamp - timedelta(seconds=1)
        device = _device(
            "192.168.1.20", timestamp - timedelta(seconds=1), timestamp + timedelta(hours=1)
        )
        session.add(device)
        await session.commit()

    assert await _run_sync(monkeypatch, session_factory, [record]) == 0
    async with session_factory() as session:
        assert len(list((await session.scalars(select(InternetActivity))).all())) == 1
