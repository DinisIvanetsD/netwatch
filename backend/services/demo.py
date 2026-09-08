from datetime import UTC, datetime, timedelta
from ipaddress import ip_network
from itertools import islice

from sqlalchemy import func, select

from core.config import settings
from database.session import SessionLocal
from models.alert import Alert
from models.device import Device, DeviceSource, DeviceStatus
from models.event import Event, EventSeverity, EventType
from models.metric import DeviceMetric
from models.service import Service

DEMO_DEVICE_TEMPLATES = (
    ("Main Router", "gateway.netwatch.demo", "A4:2B:B0:18:20:01", "TP-Link", True, 2.1),
    ("NAS Server", "nas.netwatch.demo", "00:11:32:61:20:02", "Synology", False, 3.8),
    ("Workstation", "desktop-dinis.netwatch.demo", "3C:52:82:7A:20:03", "Intel", False, 4.2),
    ("Living Room TV", "living-room-tv.netwatch.demo", "7C:64:56:33:20:04", "Samsung", False, 8.7),
    ("Office Printer", "printer.netwatch.demo", "00:80:77:55:20:05", "Brother", False, None),
    ("Laptop", "laptop.netwatch.demo", "D8:3A:DD:42:20:06", "Apple", False, 6.4),
)


async def seed_demo_devices() -> None:
    if not settings.netwatch_demo_mode:
        return

    async with SessionLocal() as session:
        existing = await session.scalar(
            select(func.count()).select_from(Device).where(Device.source == DeviceSource.DEMO)
        )
        if existing:
            return

        now = datetime.now(UTC)
        network = ip_network(settings.netwatch_subnet)
        addresses = list(islice(network.hosts(), len(DEMO_DEVICE_TEMPLATES)))
        devices: list[Device] = []

        for index, (template, address) in enumerate(
            zip(DEMO_DEVICE_TEMPLATES, addresses, strict=False)
        ):
            name, hostname, mac_address, vendor, is_gateway, latency_ms = template
            online = latency_ms is not None
            devices.append(
                Device(
                    name=name,
                    hostname=hostname,
                    ip_address=str(address),
                    mac_address=mac_address,
                    vendor=vendor,
                    status=DeviceStatus.ONLINE if online else DeviceStatus.OFFLINE,
                    source=DeviceSource.DEMO,
                    latency_ms=latency_ms,
                    first_seen=now - timedelta(days=14 - index),
                    last_seen=now
                    - (timedelta(seconds=12 + index) if online else timedelta(hours=2)),
                    is_gateway=is_gateway,
                )
            )

        session.add_all(devices)
        await session.commit()


async def seed_demo_history() -> None:
    if not settings.netwatch_demo_mode:
        return

    async with SessionLocal() as session:
        existing = await session.scalar(
            select(func.count()).select_from(Event).where(Event.source == DeviceSource.DEMO)
        )
        if existing:
            return

        devices = list(
            (
                await session.scalars(
                    select(Device).where(Device.source == DeviceSource.DEMO).order_by(Device.id)
                )
            ).all()
        )
        if not devices:
            return

        now = datetime.now(UTC)
        for device_index, device in enumerate(devices):
            for sample_index in range(24):
                online = device.status != DeviceStatus.OFFLINE or sample_index < 18
                baseline = 2.0 + device_index * 1.4
                session.add(
                    DeviceMetric(
                        device_id=device.id,
                        timestamp=now - timedelta(hours=23 - sample_index),
                        latency_ms=round(baseline + (sample_index % 5) * 0.7, 1)
                        if online
                        else None,
                        online=online,
                    )
                )

        event_templates = (
            (
                0,
                EventType.DEVICE_DISCOVERED,
                EventSeverity.INFO,
                "Main Router was first discovered.",
                13,
            ),
            (
                1,
                EventType.DEVICE_DISCOVERED,
                EventSeverity.INFO,
                "NAS Server was first discovered.",
                11,
            ),
            (
                4,
                EventType.DEVICE_OFFLINE,
                EventSeverity.MEDIUM,
                "Office Printer went offline after repeated scan misses.",
                2,
            ),
            (5, EventType.DEVICE_ONLINE, EventSeverity.INFO, "Laptop came back online.", 1),
            (1, EventType.LATENCY_INCREASED, EventSeverity.LOW, "NAS Server latency increased.", 0),
        )
        for device_index, event_type, severity, message, hours_ago in event_templates:
            device = devices[device_index]
            session.add(
                Event(
                    device_id=device.id,
                    type=event_type,
                    message=message,
                    severity=severity,
                    timestamp=now - timedelta(hours=hours_ago, minutes=device_index * 3),
                    metadata_payload={},
                    source=DeviceSource.DEMO,
                )
            )
        await session.commit()


async def seed_demo_services() -> None:
    if not settings.netwatch_demo_mode:
        return
    async with SessionLocal() as session:
        if await session.scalar(select(func.count()).select_from(Service)):
            return
        devices = list(
            (
                await session.scalars(
                    select(Device).where(Device.source == DeviceSource.DEMO).order_by(Device.id)
                )
            ).all()
        )
        now = datetime.now(UTC)
        assignments = {
            0: (53, 80, 443),
            1: (22, 80, 443, 445),
            2: (22, 3389),
            3: (80,),
            4: (80,),
            5: (22,),
        }
        names = {22: "SSH", 53: "DNS", 80: "HTTP", 443: "HTTPS", 445: "SMB", 3389: "RDP"}
        for index, ports in assignments.items():
            for port in ports:
                session.add(
                    Service(
                        device_id=devices[index].id,
                        port=port,
                        protocol="tcp",
                        service_name=names[port],
                        first_seen=now - timedelta(days=7),
                        last_seen=now - timedelta(minutes=index),
                        active=devices[index].status != DeviceStatus.OFFLINE,
                    )
                )
        await session.commit()


async def seed_demo_alerts() -> None:
    if not settings.netwatch_demo_mode:
        return
    async with SessionLocal() as session:
        if await session.scalar(
            select(func.count()).select_from(Alert).where(Alert.source == DeviceSource.DEMO)
        ):
            return
        events = list(
            (
                await session.scalars(
                    select(Event)
                    .where(Event.source == DeviceSource.DEMO)
                    .order_by(Event.timestamp.desc())
                )
            ).all()
        )
        titles = {
            EventType.DEVICE_OFFLINE: "Device offline",
            EventType.LATENCY_INCREASED: "Latency increased",
            EventType.DEVICE_DISCOVERED: "New device detected",
        }
        for event in events:
            if event.type in titles:
                session.add(
                    Alert(
                        device_id=event.device_id,
                        event_id=event.id,
                        type=event.type.value,
                        severity=event.severity,
                        title=titles[event.type],
                        description=event.message,
                        created_at=event.timestamp,
                        read=False,
                        resolved=False,
                        source=DeviceSource.DEMO,
                    )
                )
        await session.commit()
