from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from services.providers.common import (
    CapabilityUnavailableError,
    ProviderHealth,
    ProviderStatus,
)


class DNSCapability(StrEnum):
    QUERY_HISTORY = "query_history"
    PER_CLIENT_HISTORY = "per_client_history"
    DOMAIN_BLOCKING = "domain_blocking"
    CLIENT_RULES = "client_rules"
    CATEGORY_FILTERING = "category_filtering"
    SAFE_SEARCH = "safe_search"
    STATISTICS = "statistics"
    FILTER_LISTS = "filter_lists"
    DNS_ENFORCEMENT = "dns_enforcement"
    TRAFFIC_BYTES = "traffic_bytes"


@dataclass(frozen=True, slots=True)
class DNSQueryRecord:
    timestamp: datetime
    client: str
    domain: str
    query_type: str | None
    status: str
    blocked: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class DomainRuleRequest:
    domain: str
    allow: bool
    client: str | None = None


class DNSControlProvider(ABC):
    provider_id: str
    display_name: str
    capabilities: frozenset[DNSCapability]

    def supports(self, capability: DNSCapability) -> bool:
        return capability in self.capabilities

    def require(self, capability: DNSCapability) -> None:
        if not self.supports(capability):
            raise CapabilityUnavailableError(self.display_name, capability)

    @abstractmethod
    async def test_connection(self) -> ProviderHealth:
        """Return current provider connectivity without raising for expected failures."""

    async def query_history(
        self,
        *,
        limit: int = 100,
        client: str | None = None,
    ) -> list[DNSQueryRecord]:
        self.require(DNSCapability.PER_CLIENT_HISTORY if client else DNSCapability.QUERY_HISTORY)
        raise NotImplementedError

    async def add_domain_rule(self, rule: DomainRuleRequest) -> None:
        self.require(DNSCapability.CLIENT_RULES if rule.client else DNSCapability.DOMAIN_BLOCKING)
        raise NotImplementedError

    async def remove_domain_rule(self, rule: DomainRuleRequest) -> None:
        self.require(DNSCapability.CLIENT_RULES if rule.client else DNSCapability.DOMAIN_BLOCKING)
        raise NotImplementedError

    async def statistics(self) -> dict[str, object]:
        self.require(DNSCapability.STATISTICS)
        raise NotImplementedError


class UnconfiguredDNSProvider(DNSControlProvider):
    provider_id = "not_configured"
    display_name = "No DNS provider configured"
    capabilities = frozenset[DNSCapability]()

    async def test_connection(self) -> ProviderHealth:
        return ProviderHealth(
            ProviderStatus.NOT_CONFIGURED,
            "Configure AdGuard Home or Pi-hole to enable DNS activity and filtering.",
        )
