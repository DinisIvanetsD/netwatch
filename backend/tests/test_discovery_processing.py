from datetime import UTC, datetime, timedelta

from models.device import Device, DeviceSource, DeviceStatus
from models.service import Service
from services.discovery.base import DiscoveryResult
from services.scanner.service import (
    ProcessedScan,
    ScanService,
    merge_discovery_results,
    process_discovery_results,
)


def test_discovery_results_create_new_device_and_restore_known_device() -> None:
    before = datetime.now(UTC) - timedelta(minutes=5)
    now = datetime.now(UTC)
    known = Device(
        name="Known host",
        ip_address="192.168.1.10",
        mac_address="AA:BB:CC:DD:EE:10",
        hostname=None,
        vendor=None,
        status=DeviceStatus.OFFLINE,
        source=DeviceSource.LIVE,
        latency_ms=None,
        first_seen=before,
        last_seen=before,
        is_gateway=False,
    )
    results = [
        DiscoveryResult(
            ip_address="192.168.1.10",
            reachable=True,
            latency_ms=4.5,
            hostname="known.local",
        ),
        DiscoveryResult(
            ip_address="192.168.1.11",
            reachable=True,
            latency_ms=8.2,
            mac_address="AA:BB:CC:DD:EE:11",
        ),
    ]

    created = merge_discovery_results({known.ip_address: known}, results, now)

    assert known.status == DeviceStatus.ONLINE
    assert known.hostname == "known.local"
    assert known.latency_ms == 4.5
    assert known.last_seen == now
    assert len(created) == 1
    assert created[0].status == DeviceStatus.NEW
    assert created[0].ip_address == "192.168.1.11"


def test_device_requires_repeated_misses_before_offline_then_recovers() -> None:
    now = datetime.now(UTC)
    device = Device(
        name="Laptop",
        ip_address="192.168.1.20",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        latency_ms=5.0,
        first_seen=now,
        last_seen=now,
        is_gateway=False,
        missed_scans=0,
    )

    first_miss = process_discovery_results({device.ip_address: device}, [], now, 2)
    assert device.status == DeviceStatus.ONLINE
    assert not first_miss.events

    second_miss = process_discovery_results({device.ip_address: device}, [], now, 2)
    assert device.status == DeviceStatus.OFFLINE
    assert second_miss.events[0].type.value == "device.offline"

    recovered = process_discovery_results(
        {device.ip_address: device},
        [DiscoveryResult(ip_address=device.ip_address, reachable=True, latency_ms=4.0)],
        now,
        2,
    )
    assert device.status == DeviceStatus.ONLINE
    assert device.missed_scans == 0
    assert recovered.events[0].type.value == "device.online"


def test_service_observations_detect_new_and_removed_ports() -> None:
    now = datetime.now(UTC)
    device = Device(
        id=1,
        ip_address="192.168.1.20",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        first_seen=now,
        last_seen=now,
        is_gateway=False,
    )
    ssh = Service(
        device_id=1,
        port=22,
        protocol="tcp",
        service_name="SSH",
        first_seen=now,
        last_seen=now,
        active=True,
    )

    class RecordingSession:
        def __init__(self) -> None:
            self.added: list[object] = []

        def add(self, item: object) -> None:
            self.added.append(item)

    outcome = ProcessedScan()
    session = RecordingSession()
    ScanService._merge_service_observations(device, {443}, {(1, 22): ssh}, outcome, now, session)

    assert ssh.active is False
    assert isinstance(session.added[0], Service)
    assert session.added[0].port == 443
    assert {event.type.value for event in outcome.events} == {
        "service.discovered",
        "service.removed",
    }


def test_service_observations_detect_reappearing_port() -> None:
    now = datetime.now(UTC)
    device = Device(
        id=1,
        ip_address="192.168.1.20",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        first_seen=now,
        last_seen=now,
        is_gateway=False,
    )
    ssh = Service(
        device_id=1,
        port=22,
        protocol="tcp",
        service_name="SSH",
        first_seen=now,
        last_seen=now,
        active=False,
    )

    class RecordingSession:
        def add(self, item: object) -> None:
            raise AssertionError(f"Unexpected new service: {item}")

    outcome = ProcessedScan()
    ScanService._merge_service_observations(
        device, {22}, {(1, 22): ssh}, outcome, now, RecordingSession()
    )

    assert ssh.active is True
    assert len(outcome.events) == 1
    assert outcome.events[0].type.value == "service.discovered"
    assert outcome.events[0].metadata == {"port": 22, "protocol": "tcp"}
