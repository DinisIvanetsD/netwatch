import asyncio
from collections.abc import Iterable

SERVICE_NAMES = {22: "SSH", 53: "DNS", 80: "HTTP", 443: "HTTPS", 445: "SMB", 3389: "RDP"}


class TcpServiceScanner:
    async def scan(
        self,
        hosts: Iterable[str],
        ports: Iterable[int],
        concurrency: int,
        connection_timeout: float = 0.6,
    ) -> dict[str, set[int]]:
        queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        host_list = tuple(hosts)
        port_list = tuple(ports)
        for host in host_list:
            for port in port_list:
                queue.put_nowait((host, port))
        found = {host: set() for host in host_list}

        async def worker() -> None:
            while not queue.empty():
                try:
                    host, port = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(host, port), timeout=connection_timeout
                    )
                    del reader
                    found[host].add(port)
                    writer.close()
                    await writer.wait_closed()
                except (TimeoutError, OSError):
                    pass
                finally:
                    queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(min(concurrency, queue.qsize()))]
        await asyncio.gather(*workers)
        return found


tcp_service_scanner = TcpServiceScanner()
