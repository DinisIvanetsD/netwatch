from ipaddress import ip_network

import httpx
import pytest

from services.discovery.host_sensor import HostSensorDiscoveryAdapter, HostSensorError


def network_payload() -> dict[str, object]:
    return {
        "subnet": "192.168.10.0/24",
        "local_ip": "192.168.10.20",
        "gateway": "192.168.10.1",
        "dns_servers": ["192.168.10.1"],
        "interface_name": "Wi-Fi",
        "hostname": "NETWATCH-PC",
        "mac_address": "AA-BB-CC-DD-EE-FF",
        "network_id": "windows:0123456789abcdef0123456789abcdef",
    }


@pytest.mark.asyncio
async def test_host_sensor_returns_validated_network_and_devices() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-token"
        if request.url.path == "/network":
            return httpx.Response(200, json=network_payload())
        return httpx.Response(
            200,
            json={
                "network": network_payload(),
                "devices": [
                    {
                        "ip_address": "192.168.10.1",
                        "reachable": True,
                        "latency_ms": 2,
                        "mac_address": "11-22-33-44-55-66",
                        "hostname": "router.home",
                        "method": "icmp",
                        "is_gateway": True,
                        "is_local": False,
                    }
                ],
            },
        )

    adapter = HostSensorDiscoveryAdapter(
        "http://host.docker.internal:8765",
        "test-token",
        transport=httpx.MockTransport(handler),
    )

    environment = await adapter.detect_network()
    devices = await adapter.discover(ip_network(environment.subnet))

    assert environment.local_ip == "192.168.10.20"
    assert environment.mac_address == "AA:BB:CC:DD:EE:FF"
    assert environment.network_id == "windows:0123456789abcdef0123456789abcdef"
    assert devices[0].ip_address == "192.168.10.1"
    assert devices[0].mac_address == "11:22:33:44:55:66"
    assert devices[0].is_gateway is True


@pytest.mark.asyncio
async def test_host_sensor_rejects_devices_outside_authorized_subnet() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "network": network_payload(),
                "devices": [{"ip_address": "192.168.11.50", "reachable": True}],
            },
        )

    adapter = HostSensorDiscoveryAdapter(
        "http://host.docker.internal:8765",
        "test-token",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(HostSensorError, match="outside the scan subnet"):
        await adapter.discover(ip_network("192.168.10.0/24"))


@pytest.mark.asyncio
async def test_host_sensor_rejects_same_subnet_physical_network_change() -> None:
    changed = {**network_payload(), "network_id": "windows:fedcba9876543210fedcba9876543210"}

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"network": changed, "devices": []},
        )

    adapter = HostSensorDiscoveryAdapter(
        "http://host.docker.internal:8765",
        "test-token",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(HostSensorError, match="physical networks"):
        await adapter.discover(
            ip_network("192.168.10.0/24"),
            expected_network_id="windows:0123456789abcdef0123456789abcdef",
        )


@pytest.mark.asyncio
async def test_host_sensor_ignores_environment_proxies(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    real_client = httpx.AsyncClient

    def client_factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        captured.update(kwargs)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:8080")
    monkeypatch.setenv("ALL_PROXY", "http://proxy.example:8080")

    adapter = HostSensorDiscoveryAdapter(
        "http://host.docker.internal:8765",
        "test-token",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=network_payload())
        ),
    )

    await adapter.detect_network()

    assert captured["trust_env"] is False
