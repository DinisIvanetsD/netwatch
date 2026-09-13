import pytest

import services.integrations as integrations
from models.integration import Integration
from services.providers.common import ProviderStatus
from services.providers.registry import provider_registry


@pytest.mark.asyncio
async def test_invalid_persisted_router_url_keeps_provider_disconnected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    integration = Integration(
        provider_id="openwrt",
        display_name="OpenWrt",
        kind="network",
        enabled=True,
        configuration={"server_url": "http://127.0.0.1:8000/ui"},
        encrypted_credentials="stored",
    )
    previous_network = provider_registry.network
    monkeypatch.setattr(
        integrations,
        "_router_credentials",
        lambda _integration: {"username": "root", "password": "secret"},
    )
    try:
        health = await integrations.activate_router(integration)
    finally:
        provider_registry.network = previous_network

    assert health.status == ProviderStatus.ERROR
    assert "local hostname" in health.message.lower() or "path" in health.message.lower()
