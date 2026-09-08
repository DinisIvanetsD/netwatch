import asyncio
import platform
import re
import shutil
import socket
from ipaddress import IPv4Address, IPv4Network

from core.config import settings
from services.discovery.base import DiscoveryAdapter, DiscoveryResult

LATENCY_PATTERN = re.compile(r"(?:time[=<]|Average = )\s*(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)
ARP_PATTERN = re.compile(
    r"(?P<ip>\d{1,3}(?:\.\d{1,3}){3})\s+(?P<mac>[0-9a-f]{2}(?:[:-][0-9a-f]{2}){5})",
    re.IGNORECASE,
)


class SystemDiscoveryAdapter(DiscoveryAdapter):
    def __init__(self, timeout_ms: int = 900) -> None:
        self.timeout_ms = timeout_ms

    async def discover(self, network: IPv4Network) -> list[DiscoveryResult]:
        if shutil.which("ping") is None:
            raise RuntimeError(
                "Network discovery is unavailable because the system ping command is not installed."
            )

        queue: asyncio.Queue[IPv4Address] = asyncio.Queue()
        for host in network.hosts():
            queue.put_nowait(host)

        results: list[DiscoveryResult] = []
        result_lock = asyncio.Lock()

        async def worker() -> None:
            while True:
                try:
                    host = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    result = await self._probe(host)
                    if result.reachable:
                        async with result_lock:
                            results.append(result)
                finally:
                    queue.task_done()

        workers = [
            asyncio.create_task(worker())
            for _ in range(min(settings.scan_concurrency, queue.qsize()))
        ]
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            for worker_task in workers:
                worker_task.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            raise

        neighbors = await self._read_neighbors()
        for result in results:
            result.mac_address = neighbors.get(result.ip_address)
        return sorted(results, key=lambda result: IPv4Address(result.ip_address))

    async def _probe(self, host: IPv4Address) -> DiscoveryResult:
        address = str(host)
        if platform.system() == "Windows":
            command = ("ping", "-n", "1", "-w", str(self.timeout_ms), address)
        else:
            timeout_seconds = max(1, round(self.timeout_ms / 1000))
            command = ("ping", "-c", "1", "-W", str(timeout_seconds), address)

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(
                process.communicate(), timeout=(self.timeout_ms / 1000) + 1
            )
        except (FileNotFoundError, TimeoutError):
            return DiscoveryResult(ip_address=address, reachable=False)

        if process.returncode != 0:
            return DiscoveryResult(ip_address=address, reachable=False)

        output = stdout.decode(errors="replace")
        match = LATENCY_PATTERN.search(output)
        latency = float(match.group(1)) if match else None
        hostname = await self._resolve_hostname(address)
        return DiscoveryResult(
            ip_address=address,
            reachable=True,
            latency_ms=latency,
            hostname=hostname,
        )

    async def _resolve_hostname(self, address: str) -> str | None:
        try:
            hostname, _, _ = await asyncio.wait_for(
                asyncio.to_thread(socket.gethostbyaddr, address), timeout=0.5
            )
            return hostname
        except (OSError, TimeoutError):
            return None

    async def _read_neighbors(self) -> dict[str, str]:
        try:
            process = await asyncio.create_subprocess_exec(
                "arp",
                "-a",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=2)
        except (FileNotFoundError, TimeoutError):
            return {}

        neighbors: dict[str, str] = {}
        for match in ARP_PATTERN.finditer(stdout.decode(errors="replace")):
            mac = match.group("mac").replace("-", ":").upper()
            neighbors[match.group("ip")] = mac
        return neighbors
