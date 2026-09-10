from ipaddress import ip_address

from services.providers.common import ProviderHealth, ProviderStatus
from services.providers.dns.base import DNSControlProvider
from services.providers.network.base import (
    NetworkCapability,
    NetworkControlProvider,
    NetworkControlResult,
)


class DNSContainmentNetworkProvider(NetworkControlProvider):
    """Network-shaped adapter for DNS-only containment.

    This intentionally does not advertise LAN quarantine or firewall capabilities.
    """

    provider_id = "technitium_dns_containment"
    display_name = "Technitium DNS-only containment"
    identifier_kind = "ip"
    capabilities = frozenset(
        {NetworkCapability.BLOCK_INTERNET, NetworkCapability.UNBLOCK_INTERNET}
    )

    def __init__(self, dns_provider: DNSControlProvider) -> None:
        self.dns_provider = dns_provider

    async def test_connection(self) -> ProviderHealth:
        health = await self.dns_provider.test_connection()
        if health.status != ProviderStatus.CONNECTED:
            return health
        return ProviderHealth(
            health.status,
            "DNS-only containment is available. It is not router/firewall quarantine "
            "and requires each client to use Technitium DNS.",
            health.version,
        )

    @staticmethod
    def _preferred_identifier(identifier: str) -> str:
        try:
            return str(ip_address(identifier))
        except ValueError as error:
            raise ValueError("DNS containment requires the device IP address") from error

    async def block_internet(self, identifier: str) -> NetworkControlResult:
        client = self._preferred_identifier(identifier)
        reference = await self.dns_provider.contain_client_dns(client)
        return NetworkControlResult(
            True,
            "DNS-only containment applied; it is bypassable by direct IP, DoH, or VPN. "
            f"Managed reference: {reference}.",
        )

    async def unblock_internet(self, identifier: str) -> NetworkControlResult:
        client = self._preferred_identifier(identifier)
        changed = await self.dns_provider.release_client_dns(client)
        return NetworkControlResult(
            changed,
            "DNS-only containment removed; this provider never quarantines LAN access "
            "or installs firewall rules.",
        )

    async def clear_all(self) -> int:
        return await self.dns_provider.clear_client_dns_containments()


TechnitiumDNSContainmentProvider = DNSContainmentNetworkProvider
