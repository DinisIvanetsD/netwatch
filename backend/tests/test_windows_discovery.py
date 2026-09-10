import json

from services.discovery.base import DiscoveryResult, NetworkEnvironment
from services.discovery.windows import enrich_results_with_environment, parse_windows_networks


def test_parses_private_windows_network_and_normalizes_mac() -> None:
    payload = json.dumps(
        {
            "interface_name": "Wi-Fi",
            "local_ip": "192.168.50.14",
            "prefix_length": 24,
            "gateway": "192.168.50.1",
            "dns_servers": ["192.168.50.1", "1.1.1.1"],
            "hostname": "NETWATCH-PC",
            "mac_address": "aa-bb-cc-dd-ee-ff",
            "profile_id": "{NETWORK-A}",
            "gateway_mac": "11-22-33-44-55-66",
        }
    )

    environments = parse_windows_networks(payload)

    assert environments == [
        NetworkEnvironment(
            subnet="192.168.50.0/24",
            local_ip="192.168.50.14",
            gateway="192.168.50.1",
            dns_servers=("192.168.50.1", "1.1.1.1"),
            interface_name="Wi-Fi",
            hostname="NETWATCH-PC",
            mac_address="AA:BB:CC:DD:EE:FF",
            network_id=environments[0].network_id,
        )
    ]
    assert environments[0].network_id is not None
    assert environments[0].network_id.startswith("windows:")


def test_same_cidr_on_different_windows_profiles_gets_a_different_identity() -> None:
    def payload(profile_id: str) -> str:
        return json.dumps(
            {
                "interface_name": "Wi-Fi",
                "local_ip": "192.168.1.20",
                "prefix_length": 24,
                "gateway": "192.168.1.1",
                "profile_id": profile_id,
                "gateway_mac": "11-22-33-44-55-66",
            }
        )

    first = parse_windows_networks(payload("{NETWORK-A}"))[0]
    second = parse_windows_networks(payload("{NETWORK-B}"))[0]

    assert first.subnet == second.subnet
    assert first.network_id != second.network_id


def test_network_identity_survives_temporary_gateway_neighbor_loss() -> None:
    def payload(gateway_mac: str | None) -> str:
        return json.dumps(
            {
                "interface_name": "Wi-Fi",
                "local_ip": "192.168.1.20",
                "prefix_length": 24,
                "gateway": "192.168.1.1",
                "profile_id": "{NETWORK-A}",
                "gateway_mac": gateway_mac,
            }
        )

    with_gateway = parse_windows_networks(payload("11-22-33-44-55-66"))[0]
    without_gateway = parse_windows_networks(payload(None))[0]

    assert with_gateway.network_id == without_gateway.network_id


def test_ignores_non_private_or_invalid_windows_routes() -> None:
    payload = json.dumps(
        [
            {"local_ip": "203.0.113.5", "prefix_length": 24},
            {"local_ip": "not-an-ip", "prefix_length": 24},
        ]
    )

    assert parse_windows_networks(payload) == []


def test_enrichment_guarantees_local_host_without_synthesizing_gateway() -> None:
    environment = NetworkEnvironment(
        subnet="192.168.1.0/24",
        local_ip="192.168.1.43",
        gateway="192.168.1.1",
        dns_servers=("192.168.1.1",),
        interface_name="Wi-Fi",
        hostname="LAPTOP-DINIS",
        mac_address="94:B6:09:44:DD:42",
    )

    results = enrich_results_with_environment(
        [DiscoveryResult(ip_address="192.168.1.1", reachable=True)],
        environment,
    )

    assert [result.ip_address for result in results] == ["192.168.1.1", "192.168.1.43"]
    assert results[0].is_gateway is True
    assert results[1].is_local is True
    assert results[1].hostname == "LAPTOP-DINIS"
    assert results[1].mac_address == "94:B6:09:44:DD:42"


def test_enrichment_does_not_claim_unobserved_gateway_reachable() -> None:
    environment = NetworkEnvironment(
        subnet="192.168.1.0/24",
        local_ip="192.168.1.43",
        gateway="192.168.1.1",
        dns_servers=(),
        interface_name="Wi-Fi",
        hostname=None,
        mac_address=None,
    )

    results = enrich_results_with_environment(
        [DiscoveryResult(ip_address="192.168.1.43", reachable=True)], environment
    )

    assert [result.ip_address for result in results] == ["192.168.1.43"]
