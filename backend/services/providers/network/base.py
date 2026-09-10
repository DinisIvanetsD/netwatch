from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

from services.providers.common import CapabilityUnavailableError, ProviderHealth


class NetworkCapability(StrEnum):
    LIST_CLIENTS = "list_clients"
    CLIENT_STATUS = "client_status"
    BLOCK_INTERNET = "block_internet"
    UNBLOCK_INTERNET = "unblock_internet"
    QUARANTINE_DEVICE = "quarantine_device"
    RELEASE_DEVICE = "release_device"
    DISCONNECT_CLIENT = "disconnect_client"
    BANDWIDTH_METRICS = "bandwidth_metrics"
    FIREWALL_RULES = "firewall_rules"


@dataclass(frozen=True, slots=True)
class NetworkClient:
    identifier: str
    ip_address: str | None
    mac_address: str | None
    hostname: str | None
    online: bool


@dataclass(frozen=True, slots=True)
class NetworkControlResult:
    changed: bool
    message: str


class NetworkControlProvider(ABC):
    provider_id: str
    display_name: str
    capabilities: frozenset[NetworkCapability]
    identifier_kind = "mac_or_ip"

    def supports(self, capability: NetworkCapability) -> bool:
        return capability in self.capabilities

    def require(self, capability: NetworkCapability) -> None:
        if not self.supports(capability):
            raise CapabilityUnavailableError(self.display_name, capability)

    @abstractmethod
    async def test_connection(self) -> ProviderHealth:
        """Return current provider connectivity without raising for expected failures."""

    async def list_clients(self) -> list[NetworkClient]:
        self.require(NetworkCapability.LIST_CLIENTS)
        raise NotImplementedError

    async def block_internet(self, identifier: str) -> NetworkControlResult:
        self.require(NetworkCapability.BLOCK_INTERNET)
        raise NotImplementedError

    async def unblock_internet(self, identifier: str) -> NetworkControlResult:
        self.require(NetworkCapability.UNBLOCK_INTERNET)
        raise NotImplementedError

    async def quarantine_device(self, identifier: str) -> NetworkControlResult:
        self.require(NetworkCapability.QUARANTINE_DEVICE)
        raise NotImplementedError

    async def release_device(self, identifier: str) -> NetworkControlResult:
        self.require(NetworkCapability.RELEASE_DEVICE)
        raise NotImplementedError

    async def block_device(self, identifier: str) -> NetworkControlResult:
        self.require(NetworkCapability.FIREWALL_RULES)
        raise NotImplementedError
