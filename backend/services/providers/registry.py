from dataclasses import dataclass
from enum import StrEnum

from services.providers.dns import AdGuardHomeProvider, DNSControlProvider, UnconfiguredDNSProvider
from services.providers.network import GenericReadOnlyProvider, NetworkControlProvider


class ProviderKind(StrEnum):
    DNS = "dns"
    NETWORK = "network"


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    provider_id: str
    display_name: str
    kind: ProviderKind
    configured: bool
    capabilities: tuple[str, ...]


class ProviderRegistry:
    def __init__(self) -> None:
        self.dns: DNSControlProvider = UnconfiguredDNSProvider()
        self.network: NetworkControlProvider = GenericReadOnlyProvider()

    def configure_adguard(self, server_url: str, username: str, password: str) -> None:
        self.dns = AdGuardHomeProvider(server_url, username, password)

    def clear_dns(self) -> None:
        self.dns = UnconfiguredDNSProvider()

    def descriptors(self) -> list[ProviderDescriptor]:
        return [
            ProviderDescriptor(
                provider_id=self.dns.provider_id,
                display_name=self.dns.display_name,
                kind=ProviderKind.DNS,
                configured=self.dns.provider_id != "not_configured",
                capabilities=tuple(
                    sorted(capability.value for capability in self.dns.capabilities)
                ),
            ),
            ProviderDescriptor(
                provider_id=self.network.provider_id,
                display_name=self.network.display_name,
                kind=ProviderKind.NETWORK,
                configured=self.network.provider_id != "monitoring_only",
                capabilities=tuple(
                    sorted(capability.value for capability in self.network.capabilities)
                ),
            ),
        ]


provider_registry = ProviderRegistry()
