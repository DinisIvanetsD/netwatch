from services.providers.common import ProviderHealth, ProviderStatus
from services.providers.network.base import NetworkCapability, NetworkControlProvider


class GenericReadOnlyProvider(NetworkControlProvider):
    provider_id = "monitoring_only"
    display_name = "Generic / Monitoring Only"
    capabilities = frozenset[NetworkCapability]()

    async def test_connection(self) -> ProviderHealth:
        return ProviderHealth(
            ProviderStatus.CONNECTED,
            "NetWatch can monitor discovered devices, but router control is not configured.",
        )
