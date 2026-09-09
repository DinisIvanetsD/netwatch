from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import api.routes.integrations as integration_routes
from api.routes.integrations import test_technitium as run_technitium_test
from main import app
from models.integration import Integration
from schemas.integration import TechnitiumTestRequest
from services.providers.common import (
    CapabilityUnavailableError,
    ProviderHealth,
    ProviderStatus,
)
from services.providers.dns import DNSCapability, TechnitiumDNSProvider, UnconfiguredDNSProvider
from services.providers.network import GenericReadOnlyProvider, NetworkCapability


async def test_unconfigured_providers_report_honest_capabilities() -> None:
    dns = UnconfiguredDNSProvider()
    network = GenericReadOnlyProvider()

    assert (await dns.test_connection()).status == ProviderStatus.NOT_CONFIGURED
    assert (await network.test_connection()).status == ProviderStatus.CONNECTED
    assert not dns.supports(DNSCapability.QUERY_HISTORY)
    assert not network.supports(NetworkCapability.BLOCK_INTERNET)

    with pytest.raises(CapabilityUnavailableError, match="unavailable"):
        await network.block_internet("AA:BB:CC:DD:EE:FF")


def test_capability_matrix_api_is_explicit() -> None:
    previous_dns = integration_routes.provider_registry.dns
    integration_routes.provider_registry.clear_dns()
    try:
        response = TestClient(app).get("/api/integrations/capabilities")
    finally:
        integration_routes.provider_registry.dns = previous_dns

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["kind"] == "dns"
    assert items[0]["configured"] is False
    assert items[0]["capabilities"]["query_history"] is False
    assert items[1]["kind"] == "network"
    assert items[1]["capabilities"]["block_internet"] is False


async def test_technitium_connection_test_reuses_matching_stored_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    integration = Integration(
        provider_id="technitium_dns",
        display_name="Technitium DNS Server",
        kind="dns",
        enabled=True,
        configuration={
            "server_url": "http://127.0.0.1:5380",
            "username": "admin",
            "dns_port": 53,
        },
        encrypted_credentials="stored",
    )

    async def get_integration(_session: object) -> Integration:
        return integration

    async def activate(_integration: Integration) -> ProviderHealth:
        return ProviderHealth(ProviderStatus.CONNECTED, "Connected", "v1")

    provider = TechnitiumDNSProvider(
        "http://127.0.0.1:5380",
        "admin",
        "secret",
        network_cidr="192.168.1.0/24",
    )
    monkeypatch.setattr(integration_routes, "get_technitium_integration", get_integration)
    monkeypatch.setattr(integration_routes, "activate_technitium", activate)
    monkeypatch.setattr(integration_routes, "provider_registry", SimpleNamespace(dns=provider))
    response = await run_technitium_test(
        TechnitiumTestRequest(server_url="http://127.0.0.1:5380", username="admin"),
        object(),  # type: ignore[arg-type]
    )

    assert response.status == ProviderStatus.CONNECTED


async def test_technitium_connection_test_requires_password_for_changed_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    integration = Integration(
        provider_id="technitium_dns",
        display_name="Technitium DNS Server",
        kind="dns",
        enabled=True,
        configuration={
            "server_url": "http://127.0.0.1:5380",
            "username": "admin",
            "dns_port": 53,
        },
        encrypted_credentials="stored",
    )

    async def get_integration(_session: object) -> Integration:
        return integration

    monkeypatch.setattr(integration_routes, "get_technitium_integration", get_integration)
    with pytest.raises(HTTPException, match="changed connection details") as error:
        await run_technitium_test(
            TechnitiumTestRequest(server_url="http://192.168.1.2:5380", username="admin"),
            object(),  # type: ignore[arg-type]
        )
    assert error.value.status_code == 400
