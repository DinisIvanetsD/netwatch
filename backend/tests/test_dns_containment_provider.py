from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from core.config import settings
from models.device import Device, DeviceSource, DeviceStatus
from services.control.actions import (
    NetworkControlActionError,
    _identifier,
    _protected_target_reason,
    _require_current_ip_owner,
    perform_network_action,
    reconcile_network_control_identifier,
    reconcile_network_control_identifiers,
)
from services.providers.dns import DNSCapability, DNSQueryRecord, TechnitiumDNSProvider
from services.providers.dns.technitium import TechnitiumProviderError
from services.providers.network import (
    DNSContainmentNetworkProvider,
    GenericReadOnlyProvider,
    NetworkCapability,
)
from services.providers.registry import ProviderRegistry, provider_registry


def test_network_adapter_is_dns_only_and_prefers_ip_identifiers() -> None:
    dns = AsyncMock()
    dns.contain_client_dns.return_value = "technitium:containment-1"
    provider = DNSContainmentNetworkProvider(dns)

    assert provider.capabilities == frozenset(
        {NetworkCapability.BLOCK_INTERNET, NetworkCapability.UNBLOCK_INTERNET}
    )
    assert not provider.supports(NetworkCapability.QUARANTINE_DEVICE)
    assert not provider.supports(NetworkCapability.FIREWALL_RULES)
    assert provider.identifier_kind == "ip"


def test_registry_uses_dns_containment_only_as_a_router_fallback() -> None:
    registry = ProviderRegistry()

    registry.configure_technitium(
        "http://127.0.0.1:5380",
        "admin",
        "secret",
        network_cidr="192.168.1.0/24",
    )

    assert registry.dns.provider_id == "technitium_dns"
    assert registry.network.provider_id == "technitium_dns_containment"
    assert registry.network.identifier_kind == "ip"
    registry.update_network_scope("10.42.0.0/24")
    assert registry.dns.network_cidr == "10.42.0.0/24"  # type: ignore[attr-defined]

    registry.clear_dns()
    assert registry.dns.provider_id == "not_configured"
    assert registry.network.provider_id == "monitoring_only"


def test_control_actions_target_dns_containment_by_ip_not_mac() -> None:
    provider = DNSContainmentNetworkProvider(AsyncMock())
    device = SimpleNamespace(
        ip_address="192.168.1.25", mac_address="AA:BB:CC:DD:EE:FF"
    )

    assert _identifier(device, provider) == "192.168.1.25"  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_ip_controls_reject_offline_historical_devices() -> None:
    provider = DNSContainmentNetworkProvider(AsyncMock())
    device = Device(
        id=90,
        ip_address="192.168.1.25",
        status=DeviceStatus.OFFLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        network_id="legacy",
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
        is_gateway=False,
    )

    with pytest.raises(NetworkControlActionError, match="current, online owner"):
        await _require_current_ip_owner(
            AsyncMock(), device, provider, "block_internet"
        )


@pytest.mark.asyncio
async def test_ip_control_can_release_offline_device_without_releasing_reused_ip() -> None:
    provider = DNSContainmentNetworkProvider(AsyncMock())
    now = datetime.now(UTC)
    device = Device(
        id=93,
        ip_address="192.168.1.25",
        status=DeviceStatus.OFFLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        network_id="legacy",
        control_provider_id=provider.provider_id,
        control_identifier="192.168.1.25",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
    )
    result = SimpleNamespace(all=lambda: [device])
    session = SimpleNamespace(scalars=AsyncMock(return_value=result))

    await _require_current_ip_owner(session, device, provider, "release")


def test_network_control_refuses_to_block_gateway() -> None:
    device = Device(
        id=94,
        ip_address="192.168.1.1",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        network_id="legacy",
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
        is_gateway=True,
    )
    assert "gateway" in (_protected_target_reason(device) or "").lower()


@pytest.mark.asyncio
async def test_network_action_records_and_rejects_protected_gateway() -> None:
    previous = provider_registry.network
    provider_registry.network = GenericReadOnlyProvider()
    try:
        device = Device(
            id=95,
            ip_address="192.168.1.1",
            status=DeviceStatus.ONLINE,
            source=DeviceSource.LIVE,
            network_cidr="192.168.1.0/24",
            network_id="legacy",
            first_seen=datetime.now(UTC),
            last_seen=datetime.now(UTC),
            is_gateway=True,
        )
        session = SimpleNamespace(add=Mock())
        with pytest.raises(NetworkControlActionError, match="gateway"):
            await perform_network_action(session, device, "block_internet")
        session.add.assert_called_once()
    finally:
        provider_registry.network = previous


@pytest.mark.asyncio
async def test_ip_controls_reject_ambiguous_current_address_owner(monkeypatch) -> None:
    provider = DNSContainmentNetworkProvider(AsyncMock())
    now = datetime.now(UTC)
    device = Device(
        id=91,
        ip_address="192.168.1.25",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        network_id="current",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
    )
    other = Device(
        id=92,
        ip_address=device.ip_address,
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr=device.network_cidr,
        network_id=device.network_id,
        first_seen=now,
        last_seen=now,
        is_gateway=False,
    )
    monkeypatch.setattr(settings, "netwatch_network_id", "current")
    result = SimpleNamespace(all=lambda: [device, other])
    session = SimpleNamespace(scalars=AsyncMock(return_value=result))

    with pytest.raises(NetworkControlActionError, match="currently owns"):
        await _require_current_ip_owner(session, device, provider, "block_internet")


@pytest.mark.asyncio
async def test_network_adapter_messages_describe_bypassable_dns_scope() -> None:
    dns = AsyncMock()
    dns.contain_client_dns.return_value = "technitium:containment-1"
    dns.release_client_dns.return_value = True
    provider = DNSContainmentNetworkProvider(dns)

    blocked = await provider.block_internet("192.168.1.25")
    released = await provider.unblock_internet("192.168.1.25")

    dns.contain_client_dns.assert_awaited_once_with("192.168.1.25")
    dns.release_client_dns.assert_awaited_once_with("192.168.1.25")
    assert "DNS-only" in blocked.message
    assert "direct IP" in blocked.message
    assert "DoH" in blocked.message
    assert "VPN" in blocked.message
    assert "firewall" in released.message.lower()

    with pytest.raises(ValueError, match="IP address"):
        await provider.block_internet("AA:BB:CC:DD:EE:FF")


@pytest.mark.asyncio
async def test_dns_containment_follows_a_device_ip_change() -> None:
    dns = AsyncMock()
    dns.release_client_dns.return_value = True
    dns.contain_client_dns.return_value = "technitium:new-address"
    provider = DNSContainmentNetworkProvider(dns)
    device = Device(
        id=7,
        name="Laptop",
        ip_address="192.168.1.25",
        mac_address="AA:BB:CC:DD:EE:FF",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
        is_gateway=False,
        internet_access="blocked",
        control_provider_id=provider.provider_id,
        control_identifier="192.168.1.20",
    )

    class RecordingSession:
        def __init__(self) -> None:
            self.added: list[object] = []

        def add(self, value: object) -> None:
            self.added.append(value)

    session = RecordingSession()
    previous = provider_registry.network
    provider_registry.network = provider
    try:
        changed = await reconcile_network_control_identifier(
            session,  # type: ignore[arg-type]
            device,
            "192.168.1.20",
        )
    finally:
        provider_registry.network = previous

    assert changed is True
    dns.release_client_dns.assert_awaited_once_with("192.168.1.20")
    dns.contain_client_dns.assert_awaited_once_with("192.168.1.25")
    assert device.control_identifier == "192.168.1.25"
    assert device.internet_access == "blocked"
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_ip_change_releases_recycled_address_when_new_dns_path_is_unverified() -> None:
    dns = AsyncMock()
    dns.release_client_dns.return_value = True
    dns.contain_client_dns.side_effect = RuntimeError("No recent DNS evidence")
    provider = DNSContainmentNetworkProvider(dns)
    device = Device(
        id=8,
        ip_address="192.168.1.25",
        mac_address="AA:BB:CC:DD:EE:01",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
        is_gateway=False,
        internet_access="paused",
        control_provider_id=provider.provider_id,
        control_identifier="192.168.1.20",
    )

    class RecordingSession:
        def __init__(self) -> None:
            self.added: list[object] = []

        def add(self, value: object) -> None:
            self.added.append(value)

    session = RecordingSession()
    previous = provider_registry.network
    provider_registry.network = provider
    try:
        changed = await reconcile_network_control_identifier(
            session,  # type: ignore[arg-type]
            device,
            "192.168.1.20",
        )
    finally:
        provider_registry.network = previous

    assert changed is False
    dns.release_client_dns.assert_awaited_once_with("192.168.1.20")
    assert device.internet_access == "allowed"
    assert device.control_provider_id is None
    assert device.control_identifier is None
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_two_contained_devices_can_swap_addresses_without_losing_enforcement() -> None:
    dns = AsyncMock()
    dns.release_client_dns.return_value = True
    dns.contain_client_dns.side_effect = ["containment-a", "containment-b"]
    provider = DNSContainmentNetworkProvider(dns)
    now = datetime.now(UTC)
    first = Device(
        id=21,
        ip_address="192.168.1.25",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
        internet_access="blocked",
        control_provider_id=provider.provider_id,
        control_identifier="192.168.1.20",
    )
    second = Device(
        id=22,
        ip_address="192.168.1.20",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
        internet_access="blocked",
        control_provider_id=provider.provider_id,
        control_identifier="192.168.1.25",
    )
    session = SimpleNamespace(add=lambda _value: None)
    previous = provider_registry.network
    provider_registry.network = provider
    try:
        changed = await reconcile_network_control_identifiers(
            session,  # type: ignore[arg-type]
            [first, second],
            observed_device_ids={21, 22},
        )
    finally:
        provider_registry.network = previous

    assert changed == 2
    assert {call.args[0] for call in dns.release_client_dns.await_args_list} == {
        "192.168.1.20",
        "192.168.1.25",
    }
    assert {call.args[0] for call in dns.contain_client_dns.await_args_list} == {
        "192.168.1.20",
        "192.168.1.25",
    }
    assert first.control_identifier == first.ip_address
    assert second.control_identifier == second.ip_address


@pytest.mark.asyncio
async def test_containment_is_removed_when_a_new_mac_takes_the_address() -> None:
    dns = AsyncMock()
    dns.release_client_dns.return_value = True
    provider = DNSContainmentNetworkProvider(dns)
    now = datetime.now(UTC)
    previous_owner = Device(
        id=31,
        ip_address="192.168.1.20",
        mac_address="AA:AA:AA:AA:AA:AA",
        status=DeviceStatus.OFFLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
        internet_access="blocked",
        control_provider_id=provider.provider_id,
        control_identifier="192.168.1.20",
    )
    replacement = Device(
        id=32,
        ip_address="192.168.1.20",
        mac_address="BB:BB:BB:BB:BB:BB",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
    )
    session = SimpleNamespace(add=lambda _value: None)
    previous = provider_registry.network
    provider_registry.network = provider
    try:
        changed = await reconcile_network_control_identifiers(
            session,  # type: ignore[arg-type]
            [previous_owner, replacement],
            observed_device_ids={32},
        )
    finally:
        provider_registry.network = previous

    assert changed == 1
    dns.release_client_dns.assert_awaited_once_with("192.168.1.20")
    dns.contain_client_dns.assert_not_awaited()
    assert previous_owner.internet_access == "allowed"
    assert previous_owner.control_identifier is None


@pytest.mark.asyncio
async def test_failed_release_is_retried_on_the_next_scan() -> None:
    dns = AsyncMock()
    dns.release_client_dns.side_effect = [RuntimeError("temporary failure"), True]
    dns.contain_client_dns.return_value = "containment-new"
    provider = DNSContainmentNetworkProvider(dns)
    now = datetime.now(UTC)
    device = Device(
        id=41,
        ip_address="192.168.1.25",
        status=DeviceStatus.ONLINE,
        source=DeviceSource.LIVE,
        network_cidr="192.168.1.0/24",
        first_seen=now,
        last_seen=now,
        is_gateway=False,
        internet_access="blocked",
        control_provider_id=provider.provider_id,
        control_identifier="192.168.1.20",
    )
    session = SimpleNamespace(add=lambda _value: None)
    previous = provider_registry.network
    provider_registry.network = provider
    try:
        first = await reconcile_network_control_identifiers(
            session,  # type: ignore[arg-type]
            [device],
            observed_device_ids={41},
        )
        assert first == 0
        assert device.control_identifier == "192.168.1.20"
        second = await reconcile_network_control_identifiers(
            session,  # type: ignore[arg-type]
            [device],
            observed_device_ids={41},
        )
    finally:
        provider_registry.network = previous

    assert second == 1
    assert dns.release_client_dns.await_count == 2
    dns.contain_client_dns.assert_awaited_once_with("192.168.1.25")
    assert device.control_identifier == "192.168.1.25"


def test_technitium_renders_and_removes_managed_catch_all_without_manual_loss() -> None:
    provider = TechnitiumDNSProvider(
        "http://127.0.0.1:5380", "admin", "secret", network_cidr="192.168.1.0/24"
    )
    existing = {
        "localEndPointGroupMap": {"127.0.0.1": "local-bypass"},
        "networkGroupMap": {"192.168.50.0/24": "manual"},
        "groups": [{"name": "manual", "enableBlocking": False}],
    }
    rendered = provider._render_config(
        existing,
        {},
        {"containment-1": {"client": "192.168.1.25"}},
    )
    groups = {group["name"]: group for group in rendered["groups"]}
    assert rendered["networkGroupMap"]["192.168.1.25"] == (
        "netwatch-containment-192-168-1-25"
    )
    assert groups["netwatch-containment-192-168-1-25"]["blockedRegex"] == ["^.+$"]
    assert rendered["groups"][0] == {"name": "manual", "enableBlocking": False}
    assert rendered["localEndPointGroupMap"] == {"127.0.0.1": "local-bypass"}

    released = provider._render_config(existing, {}, {})
    assert released["networkGroupMap"] == {"192.168.50.0/24": "manual"}
    assert released["groups"] == [{"name": "manual", "enableBlocking": False}]


def test_technitium_containment_capability_validates_exact_private_subnet() -> None:
    provider = TechnitiumDNSProvider(
        "http://127.0.0.1:5380", "admin", "secret", network_cidr="192.168.1.0/24"
    )
    assert provider.supports(DNSCapability.DNS_CONTAINMENT)
    with pytest.raises(ValueError, match="authorized private subnet"):
        provider._validated_clients(("192.168.2.25",))
    with pytest.raises(ValueError, match="authorized private subnet"):
        provider._validated_clients(("8.8.8.8",))


def test_containment_restores_an_exact_manual_client_mapping() -> None:
    provider = TechnitiumDNSProvider(
        "http://192.168.1.2:5380", "admin", "secret", network_cidr="192.168.1.0/24"
    )
    existing = {
        "networkGroupMap": {"192.168.1.25": "manual-client"},
        "groups": [{"name": "manual-client", "enableBlocking": False}],
    }
    containment = {
        "containment-1": {"client": "192.168.1.25", "previousGroup": "manual-client"}
    }
    rendered = provider._render_config(existing, {}, containment)
    restored_input = provider._restore_previous_mapping(
        rendered, "192.168.1.25", containment["containment-1"]
    )
    released = provider._render_config(restored_input, {}, {})

    assert released["networkGroupMap"]["192.168.1.25"] == "manual-client"
    assert released["groups"] == [{"name": "manual-client", "enableBlocking": False}]


@pytest.mark.asyncio
async def test_technitium_preflight_requires_recent_per_client_evidence() -> None:
    provider = TechnitiumDNSProvider(
        "http://127.0.0.1:5380", "admin", "secret", network_cidr="192.168.1.0/24"
    )
    provider.query_history = AsyncMock(return_value=[])

    result = await provider.preflight_client_containment("192.168.1.25")

    assert result.ready is False
    assert result.evidence_count == 0
    with pytest.raises(TechnitiumProviderError, match="No recent"):
        await provider.contain_client_dns("192.168.1.25")

    provider.query_history = AsyncMock(
        return_value=[
            DNSQueryRecord(
                datetime.now(UTC), "192.168.1.25", "example.test", "A", "NoError", False
            )
        ]
    )
    result = await provider.preflight_client_containment("192.168.1.25")
    assert result.ready is True
