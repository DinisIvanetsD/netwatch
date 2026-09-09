from datetime import UTC, datetime, timedelta
from ipaddress import ip_network
from itertools import islice

from sqlalchemy import func, select

from core.config import settings
from database.session import SessionLocal
from models.alert import Alert
from models.control import AccessAudit, ControlProfile
from models.device import Device, DeviceSource, DeviceStatus
from models.event import Event, EventSeverity, EventType
from models.internet_activity import InternetActivity
from models.metric import DeviceMetric
from models.service import Service

DEMO_DEVICE_TEMPLATES = (
    (
        "Main Router",
        "gateway.netwatch.demo",
        "A4:2B:B0:18:20:01",
        "TP-Link",
        True,
        2.1,
        "router",
        None,
        "trusted",
        "Adult",
    ),
    (
        "Dinis-PC",
        "dinis-pc.netwatch.demo",
        "3C:52:82:7A:20:02",
        "Intel",
        False,
        4.2,
        "desktop",
        "Dinis",
        "trusted",
        "Adult",
    ),
    (
        "João-iPad",
        "joao-ipad.netwatch.demo",
        "D8:3A:DD:42:20:03",
        "Apple",
        False,
        7.4,
        "tablet",
        "João",
        "trusted",
        "Child",
    ),
    (
        "Kids-Laptop",
        "kids-laptop.netwatch.demo",
        "78:2B:46:33:20:04",
        "Lenovo",
        False,
        9.1,
        "laptop",
        "Children",
        "trusted",
        "Child",
    ),
    (
        "Living-Room-TV",
        "living-room-tv.netwatch.demo",
        "7C:64:56:33:20:05",
        "Samsung",
        False,
        8.7,
        "tv",
        None,
        "trusted",
        "Adult",
    ),
    (
        "PlayStation",
        "playstation.netwatch.demo",
        "00:D9:D1:55:20:06",
        "Sony",
        False,
        None,
        "game_console",
        None,
        "trusted",
        "Child",
    ),
    (
        "Unknown-Xiaomi",
        None,
        "64:CC:2E:42:20:07",
        "Xiaomi Communications",
        False,
        18.2,
        "unknown",
        None,
        "unknown",
        None,
    ),
)


async def seed_demo_devices() -> None:
    if not settings.netwatch_demo_mode:
        return

    async with SessionLocal() as session:
        existing = await session.scalar(
            select(func.count())
            .select_from(Device)
            .where(
                Device.source == DeviceSource.DEMO,
                Device.network_cidr == settings.netwatch_subnet,
            )
        )
        if existing:
            return

        now = datetime.now(UTC)
        network = ip_network(settings.netwatch_subnet)
        addresses = list(islice(network.hosts(), len(DEMO_DEVICE_TEMPLATES)))
        profiles = {
            profile.name: profile.id
            for profile in (
                await session.scalars(
                    select(ControlProfile).where(ControlProfile.source == DeviceSource.DEMO)
                )
            ).all()
        }
        devices: list[Device] = []

        for index, (template, address) in enumerate(
            zip(DEMO_DEVICE_TEMPLATES, addresses, strict=False)
        ):
            (
                name,
                hostname,
                mac_address,
                vendor,
                is_gateway,
                latency_ms,
                device_type,
                owner,
                trust_state,
                profile_name,
            ) = template
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
                    network_cidr=settings.netwatch_subnet,
                    latency_ms=latency_ms,
                    first_seen=now - timedelta(days=14 - index),
                    last_seen=now
                    - (timedelta(seconds=12 + index) if online else timedelta(hours=2)),
                    is_gateway=is_gateway,
                    device_type=device_type,
                    owner=owner,
                    trust_state=trust_state,
                    profile_id=profiles.get(profile_name) if profile_name else None,
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
        devices = [
            device for device in devices if device.network_cidr == settings.netwatch_subnet
        ]
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
                "Dinis-PC was first discovered.",
                11,
            ),
            (
                5,
                EventType.DEVICE_OFFLINE,
                EventSeverity.MEDIUM,
                "PlayStation went offline after repeated scan misses.",
                2,
            ),
            (2, EventType.DEVICE_ONLINE, EventSeverity.INFO, "João-iPad came back online.", 1),
            (
                3,
                EventType.LATENCY_INCREASED,
                EventSeverity.LOW,
                "Kids-Laptop latency increased.",
                0,
            ),
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
        if await session.scalar(
            select(func.count())
            .select_from(Service)
            .join(Device, Device.id == Service.device_id)
            .where(Device.source == DeviceSource.DEMO)
        ):
            return
        devices = list(
            (
                await session.scalars(
                    select(Device).where(Device.source == DeviceSource.DEMO).order_by(Device.id)
                )
            ).all()
        )
        devices = [
            device for device in devices if device.network_cidr == settings.netwatch_subnet
        ]
        now = datetime.now(UTC)
        assignments = {
            0: (53, 80, 443),
            1: (22, 80, 443, 445),
            2: (22, 3389),
            3: (80,),
            4: (80,),
            5: (80, 443),
            6: (),
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


async def seed_demo_internet_activity() -> None:
    if not settings.netwatch_demo_mode:
        return
    async with SessionLocal() as session:
        if await session.scalar(
            select(func.count())
            .select_from(InternetActivity)
            .join(Device, Device.id == InternetActivity.device_id)
            .where(Device.source == DeviceSource.DEMO)
        ):
            return
        devices = {
            device.name: device
            for device in (
                await session.scalars(select(Device).where(Device.source == DeviceSource.DEMO))
            ).all()
        }
        devices = {
            name: device
            for name, device in devices.items()
            if device.network_cidr == settings.netwatch_subnet
        }
        now = datetime.now(UTC)
        observations = (
            ("João-iPad", "youtube.com", "YouTube", "streaming", False, None, 4),
            ("João-iPad", "rbxcdn.com", "Roblox", "gaming", False, None, 11),
            (
                "João-iPad",
                "blocked-example.test",
                None,
                "adult_content",
                True,
                "FilteredParental",
                16,
            ),
            ("Kids-Laptop", "tiktok.com", "TikTok", "social_media", False, None, 21),
            (
                "Kids-Laptop",
                "gambling-example.test",
                None,
                "gambling",
                True,
                "FilteredBlackList",
                29,
            ),
            ("Dinis-PC", "discord.com", "Discord", "communication", False, None, 37),
            ("Living-Room-TV", "nflxvideo.net", "Netflix", "streaming", False, None, 48),
            ("PlayStation", "playstation.net", "PlayStation", "gaming", False, None, 72),
        )
        for index, (name, domain, service, category, blocked, reason, minutes_ago) in enumerate(
            observations
        ):
            device = devices.get(name)
            if device is None:
                continue
            session.add(
                InternetActivity(
                    record_key=f"demo-{device.id}-{index}",
                    device_id=device.id,
                    profile_id=device.profile_id,
                    provider_id="demo_dns",
                    timestamp=now - timedelta(minutes=minutes_ago),
                    source_ip=device.ip_address,
                    domain=domain,
                    registered_domain=domain,
                    service=service,
                    category=category,
                    protocol="dns",
                    destination_port=53,
                    query_type="A",
                    response_status="NOERROR" if not blocked else "FILTERED",
                    blocked=blocked,
                    reason=reason,
                )
            )
        unknown = devices.get("Unknown-Xiaomi")
        if unknown is not None:
            session.add(
                AccessAudit(
                    device_id=unknown.id,
                    source=DeviceSource.DEMO,
                    action="device.discovered",
                    actor="system",
                    result="completed",
                    provider_id="demo",
                    message="Unknown-Xiaomi joined the demo network.",
                    metadata_payload={"demo": True},
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
