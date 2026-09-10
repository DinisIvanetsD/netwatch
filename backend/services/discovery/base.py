from abc import ABC, abstractmethod
from dataclasses import dataclass
from ipaddress import IPv4Network


@dataclass(frozen=True, slots=True)
class NetworkEnvironment:
    subnet: str
    local_ip: str
    gateway: str | None
    dns_servers: tuple[str, ...]
    interface_name: str
    hostname: str | None = None
    mac_address: str | None = None
    network_id: str | None = None


@dataclass(slots=True)
class DiscoveryResult:
    ip_address: str
    reachable: bool
    latency_ms: float | None = None
    mac_address: str | None = None
    hostname: str | None = None
    method: str = "icmp"
    is_gateway: bool = False
    is_local: bool = False


class DiscoveryAdapter(ABC):
    @abstractmethod
    async def discover(self, network: IPv4Network) -> list[DiscoveryResult]:
        """Discover reachable hosts inside an already-authorized private network."""

    async def detect_network(self) -> NetworkEnvironment | None:
        """Return the active physical network when the adapter can prove it."""
        return None
