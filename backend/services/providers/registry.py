from dataclasses import dataclass
from enum import StrEnum

from services.providers.dns import (
    DNSControlProvider,
    TechnitiumDNSProvider,
    UnconfiguredDNSProvider,
)
from services.providers.network import (
    DNSContainmentNetworkProvider,
    GenericReadOnlyProvider,
    NetworkControlProvider,
)


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

    def configure_technitium(
        self,
        server_url: str,
        username: str,
        password: str,
        *,
        network_cidr: str,
    ) -> None:
        provider = TechnitiumDNSProvider(
            server_url,
            username,
            password,
            network_cidr=network_cidr,
        )
        self.dns = provider
        if self.network.provider_id in {"monitoring_only", "technitium_dns_containment"}:
            self.network = DNSContainmentNetworkProvider(provider)

    def clear_dns(self) -> None:
        if self.network.provider_id == "technitium_dns_containment":
            self.network = GenericReadOnlyProvider()
        self.dns = UnconfiguredDNSProvider()

    def configure_network(self, provider: NetworkControlProvider) -> None:
        self.network = provider

    def clear_network(self) -> None:
        if self.dns.provider_id == "technitium_dns":
            self.network = DNSContainmentNetworkProvider(self.dns)
        else:
            self.network = GenericReadOnlyProvider()

    def update_network_scope(self, network_cidr: str) -> None:
        if isinstance(self.dns, TechnitiumDNSProvider):
            self.dns.set_network_cidr(network_cidr)

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
