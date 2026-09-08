from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from database.base import Base
from models.alert import Alert
from models.device import Device, DeviceSource, DeviceStatus
from models.event import Event, EventSeverity, EventType
from models.service import Service
from services.alerts.lifecycle import reconcile_alerts


async def _session_factory() -> tuple[async_sessionmaker[AsyncSession], object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def test_reconcile_resolves_stale_and_duplicate_transient_alerts() -> None:
    factory, engine = await _session_factory()
    now = datetime.now(UTC)
    async with factory() as session:
        device = Device(
            ip_address="192.168.1.10",
            status=DeviceStatus.ONLINE,
            source=DeviceSource.LIVE,
            latency_ms=12,
            first_seen=now,
            last_seen=now,
            is_gateway=False,
        )
        session.add(device)
        await session.flush()
        session.add_all(
            Alert(
                device_id=device.id,
                type=alert_type,
                severity=EventSeverity.MEDIUM,
                title="Transient alert",
                description="No longer active",
                created_at=now - timedelta(minutes=index),
                read=False,
                resolved=False,
                source=DeviceSource.LIVE,
            )
            for index, alert_type in enumerate(
                [
                    EventType.DEVICE_OFFLINE.value,
                    EventType.DEVICE_OFFLINE.value,
                    EventType.LATENCY_INCREASED.value,
                ],
                start=1,
            )
        )
        await session.flush()

        created = await reconcile_alerts(
            session,
            source=DeviceSource.LIVE,
            devices=[device],
            services=[],
            events=[],
        )
        await session.commit()

        alerts = list((await session.scalars(select(Alert))).all())
        assert created == []
        assert all(alert.resolved for alert in alerts)
        assert all(alert.resolved_at is not None for alert in alerts)
    await engine.dispose()


async def test_reconcile_keeps_one_active_alert_and_scopes_services_by_port() -> None:
    factory, engine = await _session_factory()
    now = datetime.now(UTC)
    async with factory() as session:
        device = Device(
            ip_address="192.168.1.20",
            status=DeviceStatus.OFFLINE,
            source=DeviceSource.LIVE,
            latency_ms=None,
            first_seen=now,
            last_seen=now,
            is_gateway=False,
        )
        session.add(device)
        await session.flush()
        old_event = Event(
            device_id=device.id,
            type=EventType.DEVICE_OFFLINE,
            message="Device went offline.",
            severity=EventSeverity.MEDIUM,
            timestamp=now - timedelta(minutes=2),
            metadata_payload={},
            source=DeviceSource.LIVE,
        )
        session.add(old_event)
        await session.flush()
        session.add(
            Alert(
                device_id=device.id,
                event_id=old_event.id,
                type=EventType.DEVICE_OFFLINE.value,
                severity=EventSeverity.MEDIUM,
                title="Device offline",
                description=old_event.message,
                created_at=old_event.timestamp,
                read=False,
                resolved=False,
                source=DeviceSource.LIVE,
            )
        )
        new_offline_event = Event(
            device_id=device.id,
            type=EventType.DEVICE_OFFLINE,
            message="Device is still offline.",
            severity=EventSeverity.MEDIUM,
            timestamp=now,
            metadata_payload={},
            source=DeviceSource.LIVE,
        )
        ssh_event = Event(
            device_id=device.id,
            type=EventType.SERVICE_DISCOVERED,
            message="TCP 22 / SSH was newly observed.",
            severity=EventSeverity.LOW,
            timestamp=now,
            metadata_payload={"port": 22},
            source=DeviceSource.LIVE,
        )
        https_event = Event(
            device_id=device.id,
            type=EventType.SERVICE_DISCOVERED,
            message="TCP 443 / HTTPS was newly observed.",
            severity=EventSeverity.LOW,
            timestamp=now,
            metadata_payload={"port": 443},
            source=DeviceSource.LIVE,
        )
        session.add_all([new_offline_event, ssh_event, https_event])
        await session.flush()
        services = [
            Service(
                device_id=device.id,
                port=port,
                protocol="tcp",
                service_name=name,
                first_seen=now,
                last_seen=now,
                active=True,
            )
            for port, name in [(22, "SSH"), (443, "HTTPS")]
        ]

        created = await reconcile_alerts(
            session,
            source=DeviceSource.LIVE,
            devices=[device],
            services=services,
            events=[new_offline_event, ssh_event, https_event],
        )

        assert [alert.type for alert in created].count(EventType.DEVICE_OFFLINE.value) == 0
        assert [alert.type for alert in created].count(EventType.SERVICE_DISCOVERED.value) == 2
    await engine.dispose()
