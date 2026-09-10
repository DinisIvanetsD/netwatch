import asyncio
import hashlib
import json
import platform
from contextlib import suppress
from ipaddress import IPv4Address, ip_address, ip_network

from core.config import normalize_private_subnet
from services.discovery.base import DiscoveryResult, NetworkEnvironment
from services.discovery.identity import normalize_mac


async def _cleanup_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is None:
        with suppress(ProcessLookupError):
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=0.5)
        except TimeoutError:
            if process.returncode is None:
                with suppress(ProcessLookupError):
                    process.kill()
                await process.wait()
    else:
        await process.wait()


async def _communicate_with_cleanup(
    process: asyncio.subprocess.Process, deadline: float
) -> tuple[bytes, bytes]:
    try:
        return await asyncio.wait_for(process.communicate(), timeout=deadline)
    except (TimeoutError, asyncio.CancelledError):
        cleanup = asyncio.create_task(_cleanup_process(process))
        try:
            await asyncio.shield(cleanup)
        except asyncio.CancelledError:
            await cleanup
        raise

WINDOWS_NETWORK_SCRIPT = r"""
$routes = Get-NetRoute -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop |
  Where-Object { $_.NextHop -ne '0.0.0.0' } |
  Sort-Object RouteMetric
$result = foreach ($route in $routes) {
  $config = Get-NetIPConfiguration -InterfaceIndex $route.InterfaceIndex
  $address = $config.IPv4Address |
    Where-Object { $_.IPAddress -notlike '169.254.*' } |
    Select-Object -First 1
  if ($null -eq $address) { continue }
  $adapter = Get-NetAdapter -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue
  $profile = Get-NetConnectionProfile -InterfaceIndex $route.InterfaceIndex `
    -ErrorAction SilentlyContinue
  $gatewayNeighbor = Get-NetNeighbor `
    -AddressFamily IPv4 `
    -InterfaceIndex $route.InterfaceIndex `
    -IPAddress $route.NextHop `
    -ErrorAction SilentlyContinue |
    Select-Object -First 1
  $dns = Get-DnsClientServerAddress `
    -InterfaceIndex $route.InterfaceIndex `
    -AddressFamily IPv4 `
    -ErrorAction SilentlyContinue
  [pscustomobject]@{
    interface_name = $config.InterfaceAlias
    local_ip = $address.IPAddress
    prefix_length = $address.PrefixLength
    gateway = $route.NextHop
    dns_servers = @($dns.ServerAddresses)
    hostname = $env:COMPUTERNAME
    mac_address = $adapter.MacAddress
    profile_id = $profile.InstanceID
    gateway_mac = $gatewayNeighbor.LinkLayerAddress
  }
}
$result | ConvertTo-Json -Compress -Depth 4
"""


def _verified_network_id(profile_id: object, gateway_mac: object) -> str | None:
    # The Windows connection profile is stable for a saved network and remains
    # available when the neighbor cache temporarily loses the gateway MAC. Use
    # the MAC only as a fallback for hosts without a connection-profile ID.
    profile = str(profile_id or "").strip().lower()
    gateway = normalize_mac(gateway_mac)
    evidence = f"profile:{profile}" if profile else (f"gateway:{gateway}" if gateway else "")
    if not evidence:
        return None
    return f"windows:{hashlib.sha256(evidence.encode()).hexdigest()[:32]}"


def parse_windows_networks(payload: str) -> list[NetworkEnvironment]:
    try:
        decoded = json.loads(payload.lstrip("\ufeff").strip() or "[]")
    except json.JSONDecodeError as error:
        raise RuntimeError("Windows returned invalid network information") from error
    rows = decoded if isinstance(decoded, list) else [decoded]
    environments: list[NetworkEnvironment] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            local_address = ip_address(str(row["local_ip"]))
            prefix_length = int(row["prefix_length"])
            subnet = normalize_private_subnet(
                str(ip_network(f"{local_address}/{prefix_length}", strict=False))
            )
        except (KeyError, TypeError, ValueError):
            continue
        if not isinstance(local_address, IPv4Address):
            continue
        network = ip_network(subnet)
        gateway_value = row.get("gateway")
        gateway: str | None = None
        if gateway_value:
            try:
                parsed_gateway = ip_address(str(gateway_value))
            except ValueError:
                parsed_gateway = None
            if isinstance(parsed_gateway, IPv4Address) and parsed_gateway in network:
                gateway = str(parsed_gateway)
        dns_servers: list[str] = []
        raw_dns = row.get("dns_servers") or []
        if isinstance(raw_dns, str):
            raw_dns = [raw_dns]
        if isinstance(raw_dns, list):
            for value in raw_dns:
                try:
                    dns_servers.append(str(ip_address(str(value))))
                except ValueError:
                    continue
        interface_name = str(row.get("interface_name") or "Windows network").strip()
        hostname = str(row.get("hostname") or "").strip() or None
        environments.append(
            NetworkEnvironment(
                subnet=subnet,
                local_ip=str(local_address),
                gateway=gateway,
                dns_servers=tuple(dict.fromkeys(dns_servers)),
                interface_name=interface_name[:120],
                hostname=hostname[:255] if hostname else None,
                mac_address=normalize_mac(row.get("mac_address")),
                network_id=_verified_network_id(
                    row.get("profile_id"), row.get("gateway_mac")
                ),
            )
        )
    return environments


async def detect_windows_network() -> NetworkEnvironment:
    if platform.system() != "Windows":
        raise RuntimeError("The Windows host sensor can only run on Windows")
    try:
        process = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            WINDOWS_NETWORK_SCRIPT,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await _communicate_with_cleanup(process, deadline=20)
    except (FileNotFoundError, TimeoutError) as error:
        raise RuntimeError("Windows network detection did not complete") from error
    if process.returncode != 0:
        message = stderr.decode(errors="replace").strip()
        raise RuntimeError(message or "Windows network detection failed")
    environments = parse_windows_networks(stdout.decode(errors="replace"))
    if not environments:
        raise RuntimeError("No active RFC 1918 Windows network with a default gateway was found")
    return environments[0]


def enrich_results_with_environment(
    results: list[DiscoveryResult], environment: NetworkEnvironment
) -> list[DiscoveryResult]:
    by_address = {result.ip_address: result for result in results}
    local_result = by_address.get(environment.local_ip)
    if local_result is None:
        local_result = DiscoveryResult(
            ip_address=environment.local_ip,
            reachable=True,
            method="windows-interface",
        )
        results.append(local_result)
        by_address[environment.local_ip] = local_result
    local_result.is_local = True
    local_result.hostname = environment.hostname or local_result.hostname
    local_result.mac_address = environment.mac_address or local_result.mac_address

    if environment.gateway:
        gateway_result = by_address.get(environment.gateway)
        if gateway_result is not None:
            gateway_result.is_gateway = True
    return sorted(results, key=lambda result: IPv4Address(result.ip_address))
