from datetime import UTC, datetime, timedelta
from time import perf_counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import services.scanner.service as scanner_module
from database.base import Base
from models.alert import Alert
from models.control import AccessAudit, ControlProfile, DomainRule
from models.device import Device, DeviceSource, DeviceStatus
from models.device_address import DeviceAddressHistory
from models.event import Event, EventSeverity, EventType
from models.internet_activity import InternetActivity
from models.metric import DeviceMetric
from models.scan import Scan, ScanStatus
from models.service import Service
from services.discovery.base import DiscoveryResult
from services.scanner.reconciliation import consolidate_duplicate_devices
from services.scanner.service import ScanService, process_discovery_results


async def _session_factory() -> tuple[object, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def test_duplicate_mac_reconciliation_preserves_identity_and_history() -> None:
    engine, factory = await _session_factory()
    now = datetime.now(UTC)
    earlier = now - timedelta(days=2)
    try:
        async with factory() as session:
            profile = ControlProfile(
                name="Dinis",
                source=DeviceSource.LIVE,
                description="Owner profile",
                internet_enabled=True,
                safe_search_enabled=False,
                blocked_categories=[],
            )
            session.add(profile)
            await session.flush()
            stale = Device(
                name="This PC",
                ip_address="192.168.1.37",
                mac_address="94-b6-09-44-dd-42",
                status=DeviceStatus.ONLINE,
                source=DeviceSource.LIVE,
                network_cidr="192.168.1.0/24",
                first_seen=earlier,
                last_seen=now,
                is_gateway=False,
                trust_state="unknown",
            )
            keeper = Device(
                name="LAPTOP-DINIS",
                owner="Dinis",
                device_type="computer",
                profile_id=profile.id,
                trust_state="trusted",
                ip_address="192.168.1.43",
                mac_address="94:B6:09:44:DD:42",
                status=DeviceStatus.OFFLINE,
                source=DeviceSource.LIVE,
                network_cidr="192.168.1.0/24",
                first_seen=now - timedelta(days=1),
                last_seen=now - timedelta(minutes=1),
                is_gateway=False,
            )
            session.add_all([stale, keeper])
            await session.flush()
            session.add_all(
                [
                    Service(
                        device_id=stale.id,
                        port=443,
                        protocol="tcp",
                        service_name="HTTPS",
                        first_seen=earlier,
                        last_seen=now,
                        active=True,
                    ),
                    Service(
                        device_id=keeper.id,
                        port=443,
                        protocol="tcp",
                        service_name="HTTPS",
                        first_seen=now - timedelta(days=1),
                        last_seen=now - timedelta(minutes=1),
                        active=False,
                    ),
                    Service(
                        device_id=stale.id,
                        port=80,
                        protocol="tcp",
                        service_name="HTTP",
                        first_seen=earlier,
                        last_seen=now,
                        active=True,
                    ),
                    DeviceMetric(
                        device_id=stale.id,
                        timestamp=earlier,
                        latency_ms=3.0,
                        online=True,
                    ),
                ]
            )
            event = Event(
                device_id=stale.id,
                type=EventType.DEVICE_DISCOVERED,
                message="Discovered",
                severity=EventSeverity.INFO,
                timestamp=earlier,
                metadata_payload={},
                source=DeviceSource.LIVE,
            )
            session.add(event)
            await session.flush()
            session.add_all(
                [
                    Alert(
                        device_id=stale.id,
                        event_id=event.id,
                        type="new_device",
                        severity=EventSeverity.INFO,
                        title="New device",
                        description="Observed",
                        source=DeviceSource.LIVE,
                    ),
                    AccessAudit(
                        source=DeviceSource.LIVE,
                        device_id=stale.id,
                        action="trust",
                        actor="administrator",
                        result="applied",
                        message="Trusted",
                        metadata_payload={},
                    ),
                    InternetActivity(
                        record_key="duplicate-device-record",
                        device_id=stale.id,
                        provider_id="test",
                        timestamp=earlier,
                        domain="example.com",
                        category="other",
                        response_status="NOERROR",
                        blocked=False,
                    ),
                    DomainRule(
                        source=DeviceSource.LIVE,
                        scope_type="device",
                        scope_id=stale.id,
                        domain="example.com",
                        action="block",
                        include_subdomains=True,
                        enabled=True,
                        enforcement_status="active",
                    ),
                ]
            )
            await session.flush()

            remaining, changed_ids = await consolidate_duplicate_devices(
                session, [stale, keeper]
            )
            outcome = process_discovery_results(
                {device.ip_address: device for device in remaining},
                [
                    DiscoveryResult(
                        ip_address="192.168.1.37",
                        reachable=True,
                        latency_ms=2.0,
                        mac_address="94:B6:09:44:DD:42",
                        hostname="LAPTOP-DINIS",
                    )
                ],
                now,
                2,
            )
            await session.commit()

            assert remaining == [keeper]
            assert changed_ids == {keeper.id}
            assert outcome.ip_changed == [keeper]
            assert keeper.ip_address == "192.168.1.37"
            assert keeper.name == "LAPTOP-DINIS"
            assert keeper.owner == "Dinis"
            assert keeper.profile_id == profile.id
            assert keeper.trust_state == "trusted"
            assert keeper.first_seen == earlier
            assert await session.scalar(select(func.count()).select_from(Device)) == 1

            services = list((await session.scalars(select(Service).order_by(Service.port))).all())
            assert [(service.port, service.device_id) for service in services] == [
                (80, keeper.id),
                (443, keeper.id),
            ]
            https = services[1]
            assert https.first_seen.replace(tzinfo=UTC) == earlier
            assert https.last_seen.replace(tzinfo=UTC) == now
            assert https.active is True
            for model in (DeviceMetric, Event, Alert, AccessAudit, InternetActivity):
                assert set((await session.scalars(select(model.device_id))).all()) == {
                    keeper.id
                }
            rule = await session.scalar(select(DomainRule))
            assert rule is not None
            assert rule.scope_id == keeper.id
            second_pass, second_changed = await consolidate_duplicate_devices(
                session, remaining
            )
            assert second_pass == remaining
            assert second_changed == set()
    finally:
        await engine.dispose()


async def test_ip_change_reconciles_dns_rules(monkeypatch) -> None:
    engine, factory = await _session_factory()
    now = datetime.now(UTC)
    previous_subnet = scanner_module.settings.netwatch_subnet
    reconciled: list[int] = []

    async def record_reconciliation(_session, device_id: int, _source) -> None:
        reconciled.append(device_id)

    async def ignore_broadcast(*_args, **_kwargs) -> None:
        return None

    async def no_dns_activity() -> int:
        return 0

    monkeypatch.setattr(scanner_module, "SessionLocal", factory)
    monkeypatch.setattr(scanner_module, "reconcile_device_rules", record_reconciliation)
    monkeypatch.setattr(scanner_module.connection_manager, "broadcast", ignore_broadcast)
    monkeypatch.setattr(scanner_module, "sync_dns_activity", no_dns_activity)
    scanner_module.settings.netwatch_subnet = "192.168.1.0/24"
    try:
        async with factory() as session:
            device = Device(
                name="Dinis Laptop",
                owner="Dinis",
                ip_address="192.168.1.43",
                mac_address="94:B6:09:44:DD:42",
                status=DeviceStatus.ONLINE,
                source=DeviceSource.LIVE,
                network_cidr="192.168.1.0/24",
                first_seen=now,
                last_seen=now,
                is_gateway=False,
            )
            scan = Scan(
                status=ScanStatus.RUNNING,
                subnet="192.168.1.0/24",
                source=DeviceSource.LIVE,
            )
            session.add_all([device, scan])
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
            device_id = device.id
            scan_id = scan.id

        service = ScanService(discovery=object())
        await service._persist_results(
            scan_id,
            [
                DiscoveryResult(
                    ip_address="192.168.1.37",
                    reachable=True,
                    latency_ms=2.0,
                    mac_address="94:B6:09:44:DD:42",
                    hostname="LAPTOP-DINIS",
                )
            ],
            None,
            perf_counter(),
        )

        assert reconciled == [device_id]
        async with factory() as session:
            stored = await session.get(Device, device_id)
            completed = await session.get(Scan, scan_id)
            assert stored is not None
            assert stored.ip_address == "192.168.1.37"
            histories = list(
                (
                    await session.scalars(
                        select(DeviceAddressHistory)
                        .where(DeviceAddressHistory.device_id == device_id)
                        .order_by(DeviceAddressHistory.started_at)
                    )
                ).all()
            )
            assert [history.ip_address for history in histories] == [
                "192.168.1.43",
                "192.168.1.37",
            ]
            assert histories[0].ended_at is not None
            assert histories[1].ended_at is None
            assert completed is not None
            assert completed.status == ScanStatus.COMPLETED
    finally:
        scanner_module.settings.netwatch_subnet = previous_subnet
        await engine.dispose()


async def test_duplicate_mac_reconciliation_never_crosses_network_scope() -> None:
    engine, factory = await _session_factory()
    now = datetime.now(UTC)
    try:
        async with factory() as session:
            devices = [
                Device(
                    ip_address="192.168.1.20",
                    mac_address="AA:BB:CC:DD:EE:FF",
                    status=DeviceStatus.ONLINE,
                    source=DeviceSource.LIVE,
                    network_cidr="192.168.1.0/24",
                    first_seen=now,
                    last_seen=now,
                    is_gateway=False,
                ),
                Device(
                    ip_address="10.42.0.20",
                    mac_address="aa-bb-cc-dd-ee-ff",
                    status=DeviceStatus.ONLINE,
                    source=DeviceSource.LIVE,
                    network_cidr="10.42.0.0/24",
                    first_seen=now,
                    last_seen=now,
                    is_gateway=False,
                ),
            ]
            session.add_all(devices)
            await session.flush()
            remaining, changed_ids = await consolidate_duplicate_devices(session, devices)
            assert remaining == devices
            assert changed_ids == set()
            assert await session.scalar(select(func.count()).select_from(Device)) == 2
    finally:
        await engine.dispose()


async def test_historical_ip_reuse_keeps_distinct_mac_identities() -> None:
    engine, factory = await _session_factory()
    now = datetime.now(UTC)
    try:
        async with factory() as session:
            previous_occupant = Device(
                name="Previous occupant",
                ip_address="192.168.1.37",
                mac_address="00:11:22:33:44:55",
                status=DeviceStatus.OFFLINE,
                source=DeviceSource.LIVE,
                network_cidr="192.168.1.0/24",
                first_seen=now - timedelta(days=1),
                last_seen=now - timedelta(days=1),
                is_gateway=False,
            )
            laptop = Device(
                name="Dinis laptop",
                owner="Dinis",
                ip_address="192.168.1.43",
                mac_address="94:B6:09:44:DD:42",
                status=DeviceStatus.ONLINE,
                source=DeviceSource.LIVE,
                network_cidr="192.168.1.0/24",
                first_seen=now,
                last_seen=now,
                is_gateway=False,
            )
            session.add_all([previous_occupant, laptop])
            await session.flush()

            outcome = process_discovery_results(
                [previous_occupant, laptop],
                [
                    DiscoveryResult(
                        ip_address="192.168.1.37",
                        reachable=True,
                        mac_address="94:B6:09:44:DD:42",
                    )
                ],
                now,
                2,
            )
            await session.commit()

            rows = list(
                (
                    await session.scalars(
                        select(Device).where(Device.ip_address == "192.168.1.37")
                    )
                ).all()
            )
            assert outcome.observed == [laptop]
            assert {device.mac_address for device in rows} == {
                "00:11:22:33:44:55",
                "94:B6:09:44:DD:42",
            }
            assert laptop.owner == "Dinis"
    finally:
        await engine.dispose()
