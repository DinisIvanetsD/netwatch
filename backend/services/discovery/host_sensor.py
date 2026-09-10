import re
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network
from typing import Any

import httpx

from core.config import normalize_private_subnet, settings
from services.discovery.base import DiscoveryAdapter, DiscoveryResult, NetworkEnvironment
from services.discovery.identity import normalize_mac


class HostSensorError(RuntimeError):
    pass


class HostSensorDiscoveryAdapter(DiscoveryAdapter):
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.transport = transport

    async def _request(self, method: str, path: str, **kwargs: Any) -> object:
        timeout = httpx.Timeout(settings.host_sensor_timeout_seconds, connect=3, write=5, pool=3)
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=timeout,
                transport=self.transport,
                trust_env=False,
            ) as client:
                response = await client.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise HostSensorError(
                "The Windows host sensor is unavailable. Start it and try the scan again."
            ) from error
        if response.is_error:
            try:
                detail = response.json().get("detail")
            except (ValueError, AttributeError):
                detail = None
            message = (
                str(detail)
                if detail
                else f"Windows host sensor returned HTTP {response.status_code}."
            )
            raise HostSensorError(message)
        try:
            return response.json()
        except ValueError as error:
            raise HostSensorError("Windows host sensor returned invalid JSON.") from error

    @staticmethod
    def _parse_environment(payload: object) -> NetworkEnvironment:
        if not isinstance(payload, dict):
            raise HostSensorError("Windows host sensor returned invalid network information.")
        try:
            subnet = normalize_private_subnet(str(payload["subnet"]))
            local_ip = ip_address(str(payload["local_ip"]))
        except (KeyError, TypeError, ValueError) as error:
            raise HostSensorError(
                "Windows host sensor returned invalid network information."
            ) from error
        network = ip_network(subnet)
        if not isinstance(local_ip, IPv4Address) or local_ip not in network:
            raise HostSensorError("Windows host sensor returned a local IP outside its subnet.")
        gateway: str | None = None
        if payload.get("gateway"):
            try:
                parsed_gateway = ip_address(str(payload["gateway"]))
            except ValueError as error:
                raise HostSensorError("Windows host sensor returned an invalid gateway.") from error
            if not isinstance(parsed_gateway, IPv4Address) or parsed_gateway not in network:
                raise HostSensorError("Windows host sensor returned a gateway outside its subnet.")
            gateway = str(parsed_gateway)
        dns_servers: list[str] = []
        raw_dns = payload.get("dns_servers") or []
        if not isinstance(raw_dns, list):
            raise HostSensorError("Windows host sensor returned invalid DNS information.")
        for value in raw_dns:
            try:
                dns_servers.append(str(ip_address(str(value))))
            except ValueError as error:
                raise HostSensorError(
                    "Windows host sensor returned an invalid DNS server."
                ) from error
        interface_name = str(payload.get("interface_name") or "Windows network").strip()
        hostname = str(payload.get("hostname") or "").strip() or None
        network_id = str(payload.get("network_id") or "").strip() or None
        if network_id and not re.fullmatch(r"windows:[0-9a-f]{32}", network_id):
            raise HostSensorError("Windows host sensor returned an invalid network identity.")
        return NetworkEnvironment(
            subnet=subnet,
            local_ip=str(local_ip),
            gateway=gateway,
            dns_servers=tuple(dict.fromkeys(dns_servers)),
            interface_name=interface_name[:120],
            hostname=hostname[:255] if hostname else None,
            mac_address=normalize_mac(payload.get("mac_address")),
            network_id=network_id,
        )

    async def detect_network(self) -> NetworkEnvironment:
        return self._parse_environment(await self._request("GET", "/network"))

    async def discover(
        self, network: IPv4Network, *, expected_network_id: str | None = None
    ) -> list[DiscoveryResult]:
        payload = await self._request(
            "POST",
            "/discover",
            json={
                "subnet": str(network),
                "timeout_ms": 900,
                "concurrency": settings.scan_concurrency,
            },
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("devices"), list):
            raise HostSensorError("Windows host sensor returned invalid discovery results.")
        environment = self._parse_environment(payload.get("network"))
        if environment.subnet != str(network):
            raise HostSensorError("Windows host sensor changed networks during the scan.")
        if expected_network_id is not None and environment.network_id != expected_network_id:
            raise HostSensorError(
                "Windows host sensor changed physical networks during the scan. "
                "No devices were saved from this scan."
            )
        results: list[DiscoveryResult] = []
        for row in payload["devices"]:
            if not isinstance(row, dict):
                raise HostSensorError("Windows host sensor returned an invalid device record.")
            try:
                address = ip_address(str(row["ip_address"]))
            except (KeyError, ValueError) as error:
                raise HostSensorError(
                    "Windows host sensor returned an invalid device IP."
                ) from error
            if not isinstance(address, IPv4Address) or address not in network:
                raise HostSensorError(
                    "Windows host sensor returned a device outside the scan subnet."
                )
            latency_value = row.get("latency_ms")
            try:
                latency = float(latency_value) if latency_value is not None else None
            except (TypeError, ValueError) as error:
                raise HostSensorError(
                    "Windows host sensor returned invalid latency data."
                ) from error
            if latency is not None and not 0 <= latency <= 60_000:
                raise HostSensorError("Windows host sensor returned invalid latency data.")
            hostname = str(row.get("hostname") or "").strip() or None
            results.append(
                DiscoveryResult(
                    ip_address=str(address),
                    reachable=bool(row.get("reachable", True)),
                    latency_ms=latency,
                    mac_address=normalize_mac(row.get("mac_address")),
                    hostname=hostname[:255] if hostname else None,
                    method=str(row.get("method") or "windows-sensor")[:40],
                    is_gateway=bool(row.get("is_gateway")),
                    is_local=bool(row.get("is_local")),
                )
            )
        return sorted(results, key=lambda result: IPv4Address(result.ip_address))
