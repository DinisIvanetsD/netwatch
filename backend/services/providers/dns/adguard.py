import asyncio
import re
from datetime import datetime
from ipaddress import ip_address
from typing import Any

import httpx

from services.providers.common import ProviderHealth, ProviderStatus
from services.providers.dns.base import (
    DNSCapability,
    DNSControlProvider,
    DNSQueryRecord,
    DomainRuleRequest,
    SafeSearchSettings,
)
from services.providers.validation import validate_local_destination

_DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}\.?$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.?$",
    re.IGNORECASE,
)
_BLOCKING_REASONS = {
    "FilteredBlackList",
    "FilteredSafeBrowsing",
    "FilteredParental",
    "FilteredInvalid",
    "FilteredBlockedService",
}
_MANAGED_REFERENCE_PATTERN = re.compile(r"^[a-z0-9_-]{1,40}$", re.IGNORECASE)


class AdGuardProviderError(RuntimeError):
    pass


def normalize_domain(value: str) -> str:
    domain = value.strip().rstrip(".").lower()
    try:
        ascii_domain = domain.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise ValueError("Domain is not valid") from error
    if not _DOMAIN_PATTERN.fullmatch(ascii_domain):
        raise ValueError("Domain must be a valid fully qualified domain name")
    return ascii_domain


class AdGuardHomeProvider(DNSControlProvider):
    provider_id = "adguard_home"
    display_name = "AdGuard Home"
    capabilities = frozenset(
        {
            DNSCapability.QUERY_HISTORY,
            DNSCapability.PER_CLIENT_HISTORY,
            DNSCapability.DOMAIN_BLOCKING,
            DNSCapability.CLIENT_RULES,
            DNSCapability.SAFE_SEARCH,
            DNSCapability.STATISTICS,
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
        self.server_url = server_url.rstrip("/")
        self._auth = httpx.BasicAuth(username, password)
        self._client = client
        self._rules_lock = asyncio.Lock()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        await validate_local_destination(self.server_url)
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0))
        try:
            response = await client.request(
                method,
                f"{self.server_url}/control{path}",
                auth=self._auth,
                params=params,
                json=json,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response
        finally:
            if owns_client:
                await client.aclose()

    async def test_connection(self) -> ProviderHealth:
        try:
            response = await self._request("GET", "/status")
            payload = response.json()
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {401, 403}:
                return ProviderHealth(
                    ProviderStatus.AUTHENTICATION_FAILED,
                    "AdGuard Home rejected the configured credentials.",
                )
            return ProviderHealth(ProviderStatus.ERROR, "AdGuard Home returned an error.")
        except (httpx.HTTPError, ValueError) as error:
            return ProviderHealth(ProviderStatus.DISCONNECTED, str(error))

        version = payload.get("version") if isinstance(payload, dict) else None
        if not isinstance(version, str) or not version:
            return ProviderHealth(
                ProviderStatus.UNSUPPORTED_VERSION,
                "The server response is not a supported AdGuard Home API.",
            )
        return ProviderHealth(ProviderStatus.CONNECTED, "AdGuard Home is connected.", version)

    async def query_history(
        self, *, limit: int = 100, client: str | None = None
    ) -> list[DNSQueryRecord]:
        self.require(DNSCapability.PER_CLIENT_HISTORY if client else DNSCapability.QUERY_HISTORY)
        requested_limit = min(max(limit, 1), 500)
        params: dict[str, Any] = {"limit": requested_limit}
        if client:
            params["search"] = client
        response = await self._request("GET", "/querylog", params=params)
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise AdGuardProviderError("AdGuard Home returned an invalid query log response")

        records: list[DNSQueryRecord] = []
        for item in payload["data"]:
            if not isinstance(item, dict) or (client and item.get("client") != client):
                continue
            question = item.get("question")
            if not isinstance(question, dict) or not question.get("name") or not item.get("time"):
                continue
            try:
                timestamp = datetime.fromisoformat(str(item["time"]).replace("Z", "+00:00"))
            except ValueError:
                continue
            reason = item.get("reason")
            records.append(
                DNSQueryRecord(
                    timestamp=timestamp,
                    client=str(item.get("client", "")),
                    domain=str(question["name"]).rstrip(".").lower(),
                    query_type=str(question.get("type")) if question.get("type") else None,
                    status=str(item.get("status", "UNKNOWN")),
                    blocked=reason in _BLOCKING_REASONS,
                    reason=str(reason) if reason else None,
                )
            )
        return records

    async def statistics(self) -> dict[str, Any]:
        self.require(DNSCapability.STATISTICS)
        payload = (await self._request("GET", "/stats")).json()
        if not isinstance(payload, dict):
            raise AdGuardProviderError("AdGuard Home returned invalid statistics")
        return payload

    async def add_domain_rule(self, rule: DomainRuleRequest) -> bool:
        self.require(DNSCapability.DOMAIN_BLOCKING)
        if rule.client_identifiers:
            self.require(DNSCapability.CLIENT_RULES)
        return await self._change_rule(rule, remove=False)

    async def remove_domain_rule(self, rule: DomainRuleRequest) -> bool:
        self.require(DNSCapability.DOMAIN_BLOCKING)
        if rule.client_identifiers:
            self.require(DNSCapability.CLIENT_RULES)
        return await self._change_rule(rule, remove=True)

    async def upsert_managed_domain_rule(self, reference: str, rule: DomainRuleRequest) -> str:
        self.require(DNSCapability.DOMAIN_BLOCKING)
        if rule.client_identifiers:
            self.require(DNSCapability.CLIENT_RULES)
        start_marker, end_marker = self._managed_markers(reference)
        rendered = self._render_domain_rule(rule)
        async with self._rules_lock:
            rules = self._without_managed_block(await self._user_rules(), start_marker, end_marker)
            rules.extend((start_marker, rendered, end_marker))
            await self._set_user_rules(rules)
        return rendered

    async def remove_managed_domain_rule(self, reference: str) -> bool:
        start_marker, end_marker = self._managed_markers(reference)
        async with self._rules_lock:
            current = await self._user_rules()
            rules = self._without_managed_block(current, start_marker, end_marker)
            if rules == current:
                return False
            await self._set_user_rules(rules)
        return True

    async def safe_search_status(self) -> SafeSearchSettings:
        self.require(DNSCapability.SAFE_SEARCH)
        payload = (await self._request("GET", "/safesearch/status")).json()
        if not isinstance(payload, dict):
            raise AdGuardProviderError("AdGuard Home returned invalid Safe Search settings")
        return self._parse_safe_search(payload)

    async def set_safe_search(self, value: SafeSearchSettings) -> SafeSearchSettings:
        self.require(DNSCapability.SAFE_SEARCH)
        await self._request(
            "PUT",
            "/safesearch/settings",
            json={
                "enabled": value.enabled,
                "google": value.google,
                "bing": value.bing,
                "youtube": value.youtube,
                "duckduckgo": value.duckduckgo,
                "ecosia": value.ecosia,
                "pixabay": value.pixabay,
                "yandex": value.yandex,
            },
        )
        return await self.safe_search_status()

    async def _change_rule(self, rule: DomainRuleRequest, *, remove: bool) -> bool:
        rendered = self._render_domain_rule(rule)
        async with self._rules_lock:
            rules = await self._user_rules()
            if remove:
                updated = [item for item in rules if item != rendered]
            elif rendered not in rules:
                updated = [*rules, rendered]
            else:
                return False
            if updated == rules:
                return False
            await self._set_user_rules(updated)
        return True

    def _render_domain_rule(self, rule: DomainRuleRequest) -> str:
        domain = normalize_domain(rule.domain)
        if rule.allow and not rule.include_subdomains:
            raise ValueError("Exact-domain allow rules are not supported by AdGuard Home")
        pattern = f"||{domain}^" if rule.include_subdomains else domain
        rendered = f"{'@@' if rule.allow else ''}{pattern}"
        clients = rule.client_identifiers
        if clients:
            normalized_clients: list[str] = []
            for value in clients:
                address = ip_address(value)
                if not (address.is_private or address.is_loopback or address.is_link_local):
                    raise ValueError("Client rules require local IP addresses")
                normalized_clients.append(str(address))
            rendered = f"{rendered}$client={'|'.join(sorted(normalized_clients))}"
        return rendered

    async def _user_rules(self) -> list[str]:
        payload = (await self._request("GET", "/filtering/status")).json()
        current = payload.get("user_rules") if isinstance(payload, dict) else None
        if current is None:
            return []
        if not isinstance(current, list) or any(not isinstance(item, str) for item in current):
            raise AdGuardProviderError("AdGuard Home returned invalid custom filter rules")
        return list(current)

    async def _set_user_rules(self, rules: list[str]) -> None:
        await self._request("POST", "/filtering/set_rules", json={"rules": rules})

    @staticmethod
    def _managed_markers(reference: str) -> tuple[str, str]:
        if not _MANAGED_REFERENCE_PATTERN.fullmatch(reference):
            raise ValueError("Managed rule reference is invalid")
        return (
            f"! NetWatch managed rule start:{reference}",
            f"! NetWatch managed rule end:{reference}",
        )

    @staticmethod
    def _without_managed_block(rules: list[str], start_marker: str, end_marker: str) -> list[str]:
        try:
            start_index = rules.index(start_marker)
            end_index = rules.index(end_marker, start_index + 1)
        except ValueError:
            return list(rules)
        return [*rules[:start_index], *rules[end_index + 1 :]]

    @staticmethod
    def _parse_safe_search(payload: dict[str, Any]) -> SafeSearchSettings:
        return SafeSearchSettings(
            enabled=bool(payload.get("enabled", False)),
            google=bool(payload.get("google", False)),
            bing=bool(payload.get("bing", False)),
            youtube=bool(payload.get("youtube", False)),
            duckduckgo=bool(payload.get("duckduckgo", False)),
            ecosia=bool(payload.get("ecosia", False)),
            pixabay=bool(payload.get("pixabay", False)),
            yandex=bool(payload.get("yandex", False)),
        )
