"""OPNsense firewall control through its authenticated REST API."""

from ipaddress import IPv4Address, ip_address
from typing import Any

import httpx

from services.providers.common import ProviderHealth, ProviderStatus
from services.providers.network.base import (
    NetworkCapability,
    NetworkControlProvider,
    NetworkControlResult,
)
from services.providers.network.router import RouterProviderError, request_json, validate_router_url


class OPNsenseProvider(NetworkControlProvider):
    provider_id = "opnsense"
    display_name = "OPNsense"
    # OPNsense's standard pf firewall model accepts IP/network sources, not
    # Ethernet MAC sources. The control layer validates IP ownership first.
    identifier_kind = "ip"
    capabilities = frozenset(
        {
            NetworkCapability.BLOCK_INTERNET,
            NetworkCapability.UNBLOCK_INTERNET,
            NetworkCapability.RELEASE_DEVICE,
            NetworkCapability.FIREWALL_RULES,
        }
    )

    def __init__(
        self,
        server_url: str,
        api_key: str,
        api_secret: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.server_url = validate_router_url(server_url)
        self._auth = (api_key, api_secret)
        self._client = client

    async def _request(self, method: str, path: str, **kwargs: object) -> Any:
        owns = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=httpx.Timeout(8, connect=3), auth=self._auth
        )
        try:
            return await request_json(client, method, f"{self.server_url}{path}", **kwargs)
        finally:
            if owns:
                await client.aclose()

    async def _mutation(self, method: str, path: str, **kwargs: object) -> dict[str, Any]:
        payload = await self._request(method, path, **kwargs)
        if not isinstance(payload, dict):
            raise RouterProviderError(f"OPNsense returned an invalid response for {path}")
        failures = {"failed", "failure", "error", "errors", "invalid", "rejected"}
        for key in ("result", "status", "response", "error"):
            value = payload.get(key)
            if value is False:
                raise RouterProviderError(f"OPNsense rejected {path}: request failed")
            if isinstance(value, str) and value.lower() in failures:
                detail = payload.get("message", value)
                raise RouterProviderError(f"OPNsense rejected {path}: {detail}")
        if payload.get("success") is False or payload.get("valid") is False:
            detail = payload.get("message", "request failed")
            raise RouterProviderError(f"OPNsense rejected {path}: {detail}")
        errors = payload.get("errors")
        if errors:
            raise RouterProviderError(f"OPNsense rejected {path}: {errors}")
        return payload

    async def test_connection(self) -> ProviderHealth:
        try:
            payload = await self._request("GET", "/api/core/system/status")
            version = payload.get("product_version") if isinstance(payload, dict) else None
            return ProviderHealth(
                ProviderStatus.CONNECTED,
                "OPNsense API is connected.",
                version if isinstance(version, str) else None,
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {401, 403}:
                return ProviderHealth(
                    ProviderStatus.AUTHENTICATION_FAILED,
                    "OPNsense rejected the configured API credentials.",
                )
            return ProviderHealth(ProviderStatus.DISCONNECTED, "OPNsense returned an HTTP error.")
        except (httpx.HTTPError, ValueError) as error:
            return ProviderHealth(ProviderStatus.DISCONNECTED, str(error))

    def _validated_ip(self, identifier: str) -> str:
        try:
            address = ip_address(identifier.strip())
        except ValueError as error:
            raise ValueError("OPNsense control requires a valid current IPv4 address") from error
        if not isinstance(address, IPv4Address) or not address.is_private:
            raise ValueError("OPNsense control requires a private IPv4 address")
        return str(address)

    async def _set_rule(self, identifier: str, enabled: bool) -> NetworkControlResult:
        address = self._validated_ip(identifier)
        description = f"NetWatch {address}"
        payload = await self._request(
            "GET", "/api/firewall/filter/searchRule", params={"searchPhrase": description}
        )
        rows = payload.get("rows", []) if isinstance(payload, dict) else []
        existing = (
            next((row for row in rows if row.get("description") == description), None)
            if isinstance(rows, list)
            else None
        )
        if enabled and existing:
            return NetworkControlResult(
                False, "The OPNsense managed firewall rule is already applied."
            )
        if not enabled and not existing:
            return NetworkControlResult(False, "No managed OPNsense rule was present.")
        if enabled:
            await self._mutation(
                "POST",
                "/api/firewall/filter/addRule",
                json={
                    "rule": {
                        "description": description,
                        "source_net": f"{address}/32",
                        "action": "block",
                        "interface": "lan",
                        "direction": "in",
                        "ipprotocol": "inet",
                        "quick": True,
                        "enabled": True,
                    }
                },
            )
        else:
            uuid = existing.get("uuid")
            if not isinstance(uuid, str) or not uuid:
                raise RouterProviderError("OPNsense returned a managed rule without a reference")
            await self._mutation("POST", f"/api/firewall/filter/delRule/{uuid}")
        await self._mutation("POST", "/api/firewall/filter/apply")
        return NetworkControlResult(
            True,
            f"OPNsense managed firewall rule {'applied' if enabled else 'removed'} for {address}.",
        )

    async def block_internet(self, identifier: str) -> NetworkControlResult:
        return await self._set_rule(identifier, True)

    async def unblock_internet(self, identifier: str) -> NetworkControlResult:
        return await self._set_rule(identifier, False)

    async def block_device(self, identifier: str) -> NetworkControlResult:
        """Apply the same source-IP firewall rule as ``block_internet``.

        OPNsense does not prove MAC/device-wide enforcement here, so this
        method deliberately does not claim stronger quarantine semantics.
        """
        return await self._set_rule(identifier, True)

    async def release_device(self, identifier: str) -> NetworkControlResult:
        return await self._set_rule(identifier, False)
