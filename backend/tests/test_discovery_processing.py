from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

import services.network_transition as network_transition_module
import services.scanner.service as scanner_module
from core.config import settings
from models.device import Device, DeviceSource, DeviceStatus
from models.service import Service
from services.discovery.base import DiscoveryResult, NetworkEnvironment
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
        network_cidr="192.168.1.0/24",
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
    assert created[0].network_cidr == "192.168.1.0/24"


def test_device_requires_repeated_misses_before_offline_then_recovers() -> None:
    now = datetime.now(UTC)
    device = Device(
        name="Laptop",
        ip_address="192.168.1.20",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
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


def test_device_identity_follows_mac_address_when_ip_changes() -> None:
    now = datetime.now(UTC)
    device = Device(
        name="Dinis Laptop",
        owner="Dinis",
        ip_address="192.168.1.37",
        mac_address="94:B6:09:44:DD:42",
        hostname="OLD-NAME",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
        missed_scans=0,
    )

    outcome = process_discovery_results(
        {device.ip_address: device},
        [
            DiscoveryResult(
                ip_address="192.168.1.43",
                reachable=True,
                mac_address="94:B6:09:44:DD:42",
                hostname="LAPTOP-DINIS",
            )
        ],
        now,
        2,
    )

    assert not outcome.created
    assert not outcome.missed
    assert device.ip_address == "192.168.1.43"
    assert device.name == "Dinis Laptop"
    assert device.owner == "Dinis"
    assert device.hostname == "LAPTOP-DINIS"
    assert {event.metadata.get("change") for event in outcome.events} == {
        "ip_address",
        "hostname",
    }


def test_mac_identity_wins_when_a_stale_device_occupies_the_new_ip() -> None:
    now = datetime.now(UTC)
    stale_ip_record = Device(
        name="Old occupant",
        ip_address="192.168.1.37",
        mac_address="00:11:22:33:44:55",
        status=DeviceStatus.OFFLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
    )
    laptop = Device(
        name="Dinis Laptop",
        owner="Dinis",
        ip_address="192.168.1.43",
        mac_address="94-b6-09-44-dd-42",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
    )

    outcome = process_discovery_results(
        {stale_ip_record.ip_address: stale_ip_record, laptop.ip_address: laptop},
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

    assert outcome.observed == [laptop]
    assert outcome.ip_changed == [laptop]
    assert laptop.ip_address == "192.168.1.37"
    assert laptop.owner == "Dinis"
    assert stale_ip_record.missed_scans == 1


@pytest.mark.parametrize("reverse_results", [False, True])
def test_dhcp_turnover_does_not_merge_a_new_mac_into_the_previous_owner(
    reverse_results: bool,
) -> None:
    now = datetime.now(UTC)
    known = Device(
        name="Known laptop",
        owner="Dinis",
        profile_id=7,
        trust_state="trusted",
        ip_address="192.168.1.20",
        mac_address="AA:AA:AA:AA:AA:AA",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
        missed_scans=0,
    )
    results = [
        DiscoveryResult(
            ip_address="192.168.1.21",
            reachable=True,
            mac_address="AA:AA:AA:AA:AA:AA",
        ),
        DiscoveryResult(
            ip_address="192.168.1.20",
            reachable=True,
            mac_address="BB:BB:BB:BB:BB:BB",
        ),
    ]
    if reverse_results:
        results.reverse()

    outcome = process_discovery_results([known], results, now, 2)

    assert len(outcome.created) == 1
    newcomer = outcome.created[0]
    assert newcomer.mac_address == "BB:BB:BB:BB:BB:BB"
    assert newcomer.ip_address == "192.168.1.20"
    assert known.ip_address == "192.168.1.21"
    assert known.owner == "Dinis"
    assert known.profile_id == 7
    assert known.trust_state == "trusted"
    assert len({id(device) for device in outcome.observed}) == 2


def test_two_known_devices_can_swap_addresses_without_merging() -> None:
    now = datetime.now(UTC)
    first = Device(
        name="First",
        ip_address="192.168.1.20",
        mac_address="AA:AA:AA:AA:AA:AA",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
        missed_scans=0,
    )
    second = Device(
        name="Second",
        ip_address="192.168.1.21",
        mac_address="BB:BB:BB:BB:BB:BB",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
        missed_scans=0,
    )

    outcome = process_discovery_results(
        [first, second],
        [
            DiscoveryResult(
                ip_address="192.168.1.21",
                reachable=True,
                mac_address="AA:AA:AA:AA:AA:AA",
            ),
            DiscoveryResult(
                ip_address="192.168.1.20",
                reachable=True,
                mac_address="BB:BB:BB:BB:BB:BB",
            ),
        ],
        now,
        2,
    )

    assert not outcome.created
    assert first.ip_address == "192.168.1.21"
    assert second.ip_address == "192.168.1.20"
    assert len({id(device) for device in outcome.observed}) == 2


def test_previous_owner_is_immediately_displaced_when_a_new_mac_reuses_its_ip() -> None:
    now = datetime.now(UTC)
    previous_owner = Device(
        name="Previous owner",
        ip_address="192.168.1.20",
        mac_address="AA:AA:AA:AA:AA:AA",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
        missed_scans=0,
    )

    outcome = process_discovery_results(
        [previous_owner],
        [
            DiscoveryResult(
                ip_address="192.168.1.20",
                reachable=True,
                mac_address="BB:BB:BB:BB:BB:BB",
            )
        ],
        now,
        offline_threshold=3,
    )

    assert len(outcome.created) == 1
    assert outcome.displaced == [previous_owner]
    assert previous_owner.status == DeviceStatus.OFFLINE
    assert previous_owner.missed_scans == 1


def test_macless_observation_does_not_choose_between_ambiguous_history() -> None:
    now = datetime.now(UTC)
    first = Device(
        name="First historical device",
        ip_address="192.168.1.20",
        status=DeviceStatus.OFFLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now - timedelta(days=2),
        last_seen=now - timedelta(days=1),
        is_gateway=False,
    )
    second = Device(
        name="Second historical device",
        ip_address="192.168.1.20",
        status=DeviceStatus.OFFLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now - timedelta(days=1),
        last_seen=now - timedelta(hours=1),
        is_gateway=False,
    )

    outcome = process_discovery_results(
        [first, second],
        [DiscoveryResult(ip_address="192.168.1.20", reachable=True)],
        now,
        offline_threshold=3,
    )

    assert len(outcome.created) == 1
    assert outcome.observed == outcome.created
    assert first.status == DeviceStatus.OFFLINE
    assert second.status == DeviceStatus.OFFLINE


def test_service_observations_detect_new_and_removed_ports() -> None:
    now = datetime.now(UTC)
    device = Device(
        id=1,
        ip_address="192.168.1.20",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
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
        network_cidr="192.168.1.0/24",
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


async def test_failed_network_switch_does_not_publish_partial_state(monkeypatch) -> None:
    environment = NetworkEnvironment(
        subnet="10.42.0.0/24",
        local_ip="10.42.0.2",
        gateway="10.42.0.1",
        dns_servers=("10.42.0.1",),
        interface_name="Mobile hotspot",
        network_id="windows:11111111111111111111111111111111",
    )

    class Discovery:
        async def detect_network(self) -> NetworkEnvironment:
            return environment

    class FailingSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def get(self, *_args):
            return SimpleNamespace(subnet="192.168.1.0/24")

        async def merge(self, _setting) -> None:
            return None

        async def commit(self) -> None:
            raise RuntimeError("database unavailable")

    async def no_containment_to_clear(*_args, **_kwargs) -> int:
        return 0

    previous_subnet = settings.netwatch_subnet
    previous_network_id = settings.netwatch_network_id
    previous_auto_detect = settings.auto_detect_network
    settings.netwatch_subnet = "192.168.1.0/24"
    settings.netwatch_network_id = "windows:00000000000000000000000000000000"
    settings.auto_detect_network = True
    monkeypatch.setattr(scanner_module, "SessionLocal", lambda: FailingSession())
    monkeypatch.setattr(
        network_transition_module,
        "clear_dns_containment_for_network_switch",
        no_containment_to_clear,
    )
    service = ScanService(discovery=Discovery())
    try:
        with pytest.raises(RuntimeError, match="database unavailable"):
            await service._network_for_scan(1)
        assert settings.netwatch_subnet == "192.168.1.0/24"
        assert settings.netwatch_network_id == "windows:00000000000000000000000000000000"
        assert service.last_environment is None
    finally:
        settings.netwatch_subnet = previous_subnet
        settings.netwatch_network_id = previous_network_id
        settings.auto_detect_network = previous_auto_detect


async def test_manual_subnet_mode_still_records_windows_sensor_provenance() -> None:
    environment = NetworkEnvironment(
        subnet="192.168.1.0/24",
        local_ip="192.168.1.37",
        gateway="192.168.1.1",
        dns_servers=("192.168.1.1",),
        interface_name="Wi-Fi",
        network_id=settings.netwatch_network_id,
    )

    class Discovery:
        async def detect_network(self) -> NetworkEnvironment:
            return environment

    previous_subnet = settings.netwatch_subnet
    previous_auto_detect = settings.auto_detect_network
    settings.netwatch_subnet = "192.168.1.0/24"
    settings.auto_detect_network = False
    service = ScanService(discovery=Discovery())
    try:
        network = await service._network_for_scan(1)
        assert str(network) == "192.168.1.0/24"
        assert service.last_environment == environment
    finally:
        settings.netwatch_subnet = previous_subnet
        settings.auto_detect_network = previous_auto_detect
