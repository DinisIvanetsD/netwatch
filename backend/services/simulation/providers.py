from services.providers.common import ProviderHealth, ProviderStatus
from services.providers.network.base import (
    NetworkCapability,
    NetworkControlProvider,
    NetworkControlResult,
)


class SimulatedNetworkControlProvider(NetworkControlProvider):
    """Applies access controls inside the simulated network.

    Registered only while Simulation mode is active, so administrators can
    exercise pause, block, quarantine, and release flows without a real router.
    Every result is explicitly labelled as simulated.
    """

    provider_id = "simulated_router"
    display_name = "Simulated router (demo)"
    identifier_kind = "mac_or_ip"
    capabilities = frozenset[NetworkCapability](
        {
            NetworkCapability.BLOCK_INTERNET,
            NetworkCapability.UNBLOCK_INTERNET,
            NetworkCapability.QUARANTINE_DEVICE,
            NetworkCapability.RELEASE_DEVICE,
            NetworkCapability.FIREWALL_RULES,
        }
    )

    async def test_connection(self) -> ProviderHealth:
        return ProviderHealth(
            ProviderStatus.CONNECTED,
            "The simulated router accepts every control while Simulation mode is active.",
            version="demo",
        )

    async def block_internet(self, identifier: str) -> NetworkControlResult:
        return NetworkControlResult(
            True, f"Simulated router blocked Internet access for {identifier} (demo)."
        )

    async def unblock_internet(self, identifier: str) -> NetworkControlResult:
        return NetworkControlResult(
            True, f"Simulated router restored Internet access for {identifier} (demo)."
        )

    async def quarantine_device(self, identifier: str) -> NetworkControlResult:
        return NetworkControlResult(True, f"Simulated router quarantined {identifier} (demo).")

    async def release_device(self, identifier: str) -> NetworkControlResult:
        return NetworkControlResult(True, f"Simulated router released {identifier} (demo).")

    async def block_device(self, identifier: str) -> NetworkControlResult:
        return NetworkControlResult(
            True, f"Simulated router added a blocking firewall rule for {identifier} (demo)."
        )
