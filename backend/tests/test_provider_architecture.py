import pytest
from fastapi.testclient import TestClient

from main import app
from services.providers.common import CapabilityUnavailableError, ProviderStatus
from services.providers.dns import DNSCapability, UnconfiguredDNSProvider
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
    response = TestClient(app).get("/api/integrations/capabilities")

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["kind"] == "dns"
    assert items[0]["configured"] is False
    assert items[0]["capabilities"]["query_history"] is False
    assert items[1]["kind"] == "network"
    assert items[1]["capabilities"]["block_internet"] is False
