from abc import ABC, abstractmethod
from dataclasses import dataclass
from ipaddress import IPv4Network


@dataclass(slots=True)
class DiscoveryResult:
    ip_address: str
    reachable: bool
    latency_ms: float | None = None
    mac_address: str | None = None
    hostname: str | None = None
    method: str = "icmp"


class DiscoveryAdapter(ABC):
    @abstractmethod
    async def discover(self, network: IPv4Network) -> list[DiscoveryResult]:
        """Discover reachable hosts inside an already-authorized private network."""
