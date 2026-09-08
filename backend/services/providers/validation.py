import asyncio
import socket
from ipaddress import ip_address
from urllib.parse import urlsplit, urlunsplit


class ProviderURLValidationError(ValueError):
    pass


def normalize_local_provider_url(value: str) -> str:
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise ProviderURLValidationError("Provider URL must use http or https")
    if not parsed.hostname or parsed.username or parsed.password:
        raise ProviderURLValidationError(
            "Provider URL must contain only a hostname and optional port"
        )
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ProviderURLValidationError("Provider URL must not contain a path, query, or fragment")
    try:
        port = parsed.port
    except ValueError as error:
        raise ProviderURLValidationError("Provider URL has an invalid port") from error
    if port is not None and not 1 <= port <= 65535:
        raise ProviderURLValidationError("Provider URL has an invalid port")

    host = parsed.hostname.rstrip(".").lower()
    try:
        address = ip_address(host)
    except ValueError:
        if "." in host and not host.endswith((".local", ".lan", ".home", ".internal")):
            raise ProviderURLValidationError(
                "Provider hostname must be local (for example adguard.local)"
            ) from None
    else:
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise ProviderURLValidationError("Provider URL must resolve to a local address")

    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc = f"{netloc}:{port}"
    return urlunsplit((parsed.scheme, netloc, "", "", ""))


async def validate_local_destination(url: str) -> None:
    parsed = urlsplit(url)
    assert parsed.hostname is not None
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    loop = asyncio.get_running_loop()
    try:
        results = await loop.getaddrinfo(
            parsed.hostname, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
        )
    except OSError as error:
        raise ProviderURLValidationError("Provider hostname could not be resolved") from error
    addresses = {ip_address(result[4][0]) for result in results}
    if not addresses or any(
        not (address.is_private or address.is_loopback or address.is_link_local)
        for address in addresses
    ):
        raise ProviderURLValidationError("Provider hostname resolved outside the local network")
