"""OpenWrt firewall control through the documented ubus JSON-RPC API."""

from typing import Any

import httpx

from services.providers.common import ProviderHealth, ProviderStatus
from services.providers.network.base import (
    NetworkCapability,
    NetworkControlProvider,
    NetworkControlResult,
)
from services.providers.network.router import RouterProviderError, request_json, validate_router_url


class OpenWrtProvider(NetworkControlProvider):
    provider_id = "openwrt"
    display_name = "OpenWrt"
    identifier_kind = "mac"
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
        username: str,
        password: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.server_url = validate_router_url(server_url)
        self.username = username
        self._password = password
        self._client = client
        self._session: str | None = None

    async def _call(self, object_name: str, method: str, params: dict[str, Any]) -> dict[str, Any]:
        owns = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(8, connect=3))
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "call",
                "params": [self._session or "0" * 32, object_name, method, params],
            }
            result = await request_json(client, "POST", f"{self.server_url}/ubus", json=payload)
        finally:
            if owns:
                await client.aclose()
        if not isinstance(result, dict) or result.get("jsonrpc") != "2.0":
            raise RouterProviderError("OpenWrt returned an invalid ubus response")
        ubus_result = result.get("result")
        if not isinstance(ubus_result, list) or not ubus_result or ubus_result[0] != 0:
            raise RouterProviderError("OpenWrt rejected the ubus request")
        # Successful ubus calls such as commit may return only [0].
        value = ubus_result[1] if len(ubus_result) > 1 else {}
        return value if isinstance(value, dict) else {}

    async def _login(self) -> None:
        result = await self._call(
            "session",
            "login",
            {"username": self.username, "password": self._password, "timeout": 300},
        )
        self._session = result.get("ubus_rpc_session")
        if not self._session:
            raise RouterProviderError("OpenWrt did not return a ubus session")

    def _name(self, identifier: str) -> str:
        return f"netwatch-{identifier.lower().replace(':', '')}"

    def _full_name(self, identifier: str) -> str:
        return f"{self._name(identifier)}-device"

    def _managed_sections(
        self, values: object, identifier: str, *, full_device: bool | None = None
    ) -> list[str]:
        names = {self._name(identifier)}
        if full_device is True:
            names = {self._full_name(identifier)}
        elif full_device is None:
            names.add(self._full_name(identifier))

        if isinstance(values, list):
            rows = ((None, row) for row in values)
        elif isinstance(values, dict):
            rows = values.items()
        else:
            return []

        sections: list[str] = []
        for section_key, row in rows:
            if not isinstance(row, dict) or row.get("name") not in names:
                continue
            section = row.get(".name", section_key)
            if isinstance(section, str) and section:
                sections.append(section)
        return sections

    async def test_connection(self) -> ProviderHealth:
        try:
            await self._login()
            return ProviderHealth(ProviderStatus.CONNECTED, "OpenWrt ubus is connected.")
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {401, 403}:
                return ProviderHealth(
                    ProviderStatus.AUTHENTICATION_FAILED,
                    "OpenWrt rejected the configured credentials.",
                )
            return ProviderHealth(ProviderStatus.DISCONNECTED, "OpenWrt returned an HTTP error.")
        except (httpx.HTTPError, RouterProviderError, ValueError) as error:
            return ProviderHealth(ProviderStatus.DISCONNECTED, str(error))

    async def _set_rule(
        self,
        identifier: str,
        enabled: bool,
        *,
        full_device: bool = False,
        remove_all: bool = False,
    ) -> NetworkControlResult:
        mac = self.validate_identifier(identifier)
        await self._login()
        name = self._full_name(mac) if full_device else self._name(mac)
        existing = await self._call("uci", "get", {"config": "firewall", "type": "rule"})
        sections = existing.get("values", [])
        matching_sections = self._managed_sections(
            sections,
            mac,
            full_device=full_device if enabled or not remove_all else None,
        )
        section = matching_sections[0] if matching_sections else None
        if not enabled and not section:
            return NetworkControlResult(False, "No managed OpenWrt rule was present.")
        if enabled and section:
            return NetworkControlResult(False, "The OpenWrt firewall rule is already applied.")
        if enabled:
            values = {
                "name": name,
                "src": "lan",
                "src_mac": mac,
                "target": "DROP",
                "enabled": "1",
            }
            if not full_device:
                values["dest"] = "wan"
            await self._call(
                "uci",
                "add",
                {
                    "config": "firewall",
                    "type": "rule",
                    "values": values,
                },
            )
        else:
            for section in matching_sections:
                await self._call("uci", "delete", {"config": "firewall", "section": section})
        await self._call("uci", "commit", {"config": "firewall"})
        return NetworkControlResult(
            True, f"OpenWrt managed firewall rule {'applied' if enabled else 'removed'} for {mac}."
        )

    async def block_internet(self, identifier: str) -> NetworkControlResult:
        return await self._set_rule(identifier, True)

    async def unblock_internet(self, identifier: str) -> NetworkControlResult:
        return await self._set_rule(identifier, False)

    async def block_device(self, identifier: str) -> NetworkControlResult:
        """Apply a LAN-source DROP rule for all destinations for this MAC.

        This is a firewall rule, not a network quarantine: it only proves
        blocking traffic entering the firewall from the LAN source MAC.
        """
        return await self._set_rule(identifier, True, full_device=True)

    async def release_device(self, identifier: str) -> NetworkControlResult:
        # Release must clean up both managed rule variants, including a prior
        # internet-only block and a full-device block.
        return await self._set_rule(identifier, False, remove_all=True)
