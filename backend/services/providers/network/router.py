"""Shared safety and HTTP helpers for authenticated router providers."""

from ipaddress import ip_address
from urllib.parse import urlsplit

import httpx

from services.providers.validation import ProviderURLValidationError, validate_local_destination


def validate_router_url(value: str) -> str:
    candidate = value.strip().rstrip("/")
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ProviderURLValidationError("Router URL must use http or https")
    if (
        parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ProviderURLValidationError(
            "Router URL must contain only a local hostname and optional port"
        )
    try:
        port = parsed.port
    except ValueError as error:
        raise ProviderURLValidationError("Router URL has an invalid port") from error
    host = parsed.hostname.rstrip(".").lower()
    try:
        address = ip_address(host)
    except ValueError:
        if "." in host and not host.endswith((".local", ".lan", ".home", ".internal")):
            raise ProviderURLValidationError("Router hostname must be local") from None
    else:
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise ProviderURLValidationError("Router URL must resolve to a local address")
    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc += f":{port}"
    return f"{parsed.scheme}://{netloc}"


async def ensure_local_router(url: str) -> None:
    await validate_local_destination(url)


class RouterProviderError(RuntimeError):
    pass


async def request_json(
    client: httpx.AsyncClient, method: str, url: str, **kwargs: object
) -> object:
    await ensure_local_router(url)
    response = await client.request(method, url, **kwargs)
    response.raise_for_status()
    return response.json()
