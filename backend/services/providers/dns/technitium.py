import asyncio
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address, ip_network
from typing import Any

import httpx

from services.providers.common import ProviderHealth, ProviderStatus
from services.providers.dns.base import (
    DNSCapability,
    DNSContainmentPreflight,
    DNSControlProvider,
    DNSQueryRecord,
    DomainRuleRequest,
)
from services.providers.dns.validation import normalize_domain
from services.providers.validation import ProviderURLValidationError, validate_local_destination

_BLOCKED_RESPONSE_TYPES = {"Blocked", "UpstreamBlocked", "CacheBlocked"}
_MANAGED_REFERENCE_PATTERN = re.compile(r"^[a-z0-9_-]{1,40}$", re.IGNORECASE)
_NETWATCH_GROUP_PREFIX = "netwatch-"
_NETWATCH_RULES_KEY = "netwatchManagedRules"
_NETWATCH_CONTAINMENTS_KEY = "netwatchManagedContainments"
_PRIVATE_DNS_CLIENTS = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8")


class TechnitiumProviderError(RuntimeError):
    pass


class TechnitiumAuthenticationError(TechnitiumProviderError):
    pass


class TechnitiumDNSProvider(DNSControlProvider):
    provider_id = "technitium_dns"
    display_name = "Technitium DNS Server"
    capabilities = frozenset(
        {
            DNSCapability.QUERY_HISTORY,
            DNSCapability.PER_CLIENT_HISTORY,
            DNSCapability.DOMAIN_BLOCKING,
            DNSCapability.CLIENT_RULES,
            DNSCapability.STATISTICS,
            DNSCapability.DNS_CONTAINMENT,
        }
    )

    def __init__(
        self,
        server_url: str,
        username: str,
        password: str,
        *,
        network_cidr: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.username = username
        self._password = password
        self.network_cidr = str(ip_network(network_cidr, strict=True))
        self._client = client
        self._token: str | None = None
        self._login_lock = asyncio.Lock()
        self._rules_lock = asyncio.Lock()

    async def _http_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        await validate_local_destination(self.server_url)
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=3.0))
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = await client.request(
                method,
                f"{self.server_url}{path}",
                params=params,
                data=data,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        finally:
            if owns_client:
                await client.aclose()
        if not isinstance(payload, dict):
            raise TechnitiumProviderError("Technitium returned an invalid API response")
        return payload

    async def _login(self, *, force: bool = False) -> dict[str, Any]:
        async with self._login_lock:
            if self._token and not force:
                return {"token": self._token, "status": "ok"}
            payload = await self._http_request(
                "POST",
                "/api/user/login",
                data={
                    "user": self.username,
                    "pass": self._password,
                    "includeInfo": "true",
                },
            )
            status = payload.get("status")
            if status != "ok":
                message = str(payload.get("errorMessage") or "Technitium rejected the credentials")
                if status in {"invalid-token", "2fa-required"} or "password" in message.lower():
                    raise TechnitiumAuthenticationError(message)
                raise TechnitiumProviderError(message)
            token = payload.get("token")
            if not isinstance(token, str) or not token:
                raise TechnitiumProviderError("Technitium did not return a session token")
            self._token = token
            return payload

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        await self._login()
        payload = await self._http_request(
            method,
            path,
            params=params,
            data=data,
            token=self._token,
        )
        if payload.get("status") == "invalid-token":
            self._token = None
            await self._login(force=True)
            payload = await self._http_request(
                method,
                path,
                params=params,
                data=data,
                token=self._token,
            )
        if payload.get("status") != "ok":
            message = str(payload.get("errorMessage") or "Technitium API request failed")
            if payload.get("status") in {"invalid-token", "2fa-required"}:
                raise TechnitiumAuthenticationError(message)
            raise TechnitiumProviderError(message)
        return payload

    async def test_connection(self) -> ProviderHealth:
        try:
            payload = await self._login(force=True)
        except TechnitiumAuthenticationError:
            return ProviderHealth(
                ProviderStatus.AUTHENTICATION_FAILED,
                "Technitium DNS Server rejected the configured credentials.",
            )
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {401, 403}:
                return ProviderHealth(
                    ProviderStatus.AUTHENTICATION_FAILED,
                    "Technitium DNS Server rejected the configured credentials.",
                )
            return ProviderHealth(ProviderStatus.ERROR, "Technitium DNS Server returned an error.")
        except (httpx.HTTPError, ProviderURLValidationError, TechnitiumProviderError) as error:
            return ProviderHealth(ProviderStatus.DISCONNECTED, str(error))

        info = payload.get("info")
        version = info.get("version") if isinstance(info, dict) else None
        if not isinstance(version, str) or not version:
            return ProviderHealth(
                ProviderStatus.UNSUPPORTED_VERSION,
                "The server response is not a supported Technitium DNS API.",
            )
        return ProviderHealth(
            ProviderStatus.CONNECTED,
            "Technitium DNS Server is connected.",
            version,
        )

    async def ensure_required_apps(self) -> tuple[str, str]:
        apps = await self._installed_apps()
        query_logger = self._query_logger(apps)
        advanced = self._advanced_blocking_app(apps)
        if query_logger and advanced:
            return query_logger[0], advanced

        response = (await self._request("GET", "/api/apps/listStoreApps")).get("response")
        store_apps = response.get("storeApps") if isinstance(response, dict) else None
        if not isinstance(store_apps, list):
            raise TechnitiumProviderError("Technitium App Store did not return an app list")

        if not query_logger:
            candidate = self._store_app(
                store_apps,
                lambda name: "query logs" in name and "sqlite" in name,
            ) or self._store_app(store_apps, lambda name: "query logs" in name)
            if candidate is None:
                raise TechnitiumProviderError("A Technitium Query Logs app was not found")
            await self._install_store_app(candidate)

        if not advanced:
            candidate = self._store_app(store_apps, lambda name: name == "advanced blocking")
            if candidate is None:
                raise TechnitiumProviderError("The Technitium Advanced Blocking app was not found")
            await self._install_store_app(candidate)

        apps = await self._installed_apps()
        query_logger = self._query_logger(apps)
        advanced = self._advanced_blocking_app(apps)
        if not query_logger or not advanced:
            raise TechnitiumProviderError("Technitium did not activate the required DNS apps")
        return query_logger[0], advanced

    async def query_history(
        self,
        *,
        limit: int = 100,
        client: str | None = None,
    ) -> list[DNSQueryRecord]:
        self.require(DNSCapability.PER_CLIENT_HISTORY if client else DNSCapability.QUERY_HISTORY)
        query_logger = self._query_logger(await self._installed_apps())
        if query_logger is None:
            raise TechnitiumProviderError(
                "Technitium Query Logs is not installed; save the integration to provision it."
            )
        app_name, class_path = query_logger
        params: dict[str, Any] = {
            "name": app_name,
            "classPath": class_path,
            "pageNumber": 1,
            "entriesPerPage": min(max(limit, 1), 500),
            "descendingOrder": "true",
        }
        if client:
            params["clientIpAddress"] = client
        response = (await self._request("GET", "/api/logs/query", params=params)).get("response")
        entries = response.get("entries") if isinstance(response, dict) else None
        if not isinstance(entries, list):
            raise TechnitiumProviderError("Technitium returned an invalid query log response")

        records: list[DNSQueryRecord] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            timestamp = self._parse_timestamp(item.get("timestamp"))
            domain = str(item.get("qname") or "").strip().rstrip(".").lower()
            client_address = self._normalize_client(item.get("clientIpAddress"))
            if timestamp is None or not domain or not client_address:
                continue
            if client and client_address != client:
                continue
            response_type = str(item.get("responseType") or "Unknown")
            blocked = response_type in _BLOCKED_RESPONSE_TYPES
            records.append(
                DNSQueryRecord(
                    timestamp=timestamp,
                    client=client_address,
                    domain=domain,
                    query_type=str(item.get("qtype")) if item.get("qtype") else None,
                    status=str(item.get("rcode") or "Unknown"),
                    blocked=blocked,
                    reason=response_type if blocked else None,
                )
            )
        return records

    async def statistics(self) -> dict[str, object]:
        self.require(DNSCapability.STATISTICS)
        payload = await self._request(
            "GET",
            "/api/dashboard/stats/get",
            params={"type": "LastHour", "utc": "true"},
        )
        response = payload.get("response")
        if not isinstance(response, dict):
            raise TechnitiumProviderError("Technitium returned invalid statistics")
        return response

    async def preflight_client_containment(
        self, client: str, *, max_age_seconds: int = 300
    ) -> DNSContainmentPreflight:
        normalized = self._validated_clients((client,))[0]
        records = await self.query_history(limit=20, client=normalized)
        cutoff = datetime.now(UTC) - timedelta(seconds=max(1, max_age_seconds))
        recent = [record for record in records if record.timestamp >= cutoff]
        if recent:
            return DNSContainmentPreflight(
                normalized, True, len(recent), "Recent per-client DNS query evidence found."
            )
        return DNSContainmentPreflight(
            normalized,
            False,
            0,
            "No recent per-client DNS query evidence; containment was not applied.",
        )

    async def contain_client_dns(self, client: str) -> str:
        preflight = await self.preflight_client_containment(client)
        if not preflight.ready:
            raise TechnitiumProviderError(preflight.message)
        normalized = preflight.client
        reference = self._containment_reference(normalized)
        async with self._rules_lock:
            app_name = await self._advanced_app_name()
            config = await self._get_app_config(app_name)
            state = self._managed_containments(config)
            if reference not in state:
                entry: dict[str, Any] = {"client": normalized}
                mappings = config.get("networkGroupMap")
                previous_group = mappings.get(normalized) if isinstance(mappings, dict) else None
                if (
                    isinstance(previous_group, str)
                    and not previous_group.startswith(_NETWATCH_GROUP_PREFIX)
                ):
                    entry["previousGroup"] = previous_group
                state[reference] = entry
            await self._set_managed_config(app_name, config, self._managed_rules(config), state)
        return f"technitium:{reference}"

    async def release_client_dns(self, client: str) -> bool:
        normalized = self._validated_clients((client,))[0]
        reference = self._containment_reference(normalized)
        async with self._rules_lock:
            app_name = await self._advanced_app_name()
            config = await self._get_app_config(app_name)
            containments = self._managed_containments(config)
            entry = containments.get(reference)
            if entry is None:
                return False
            del containments[reference]
            config = self._restore_previous_mapping(config, normalized, entry)
            await self._set_managed_config(
                app_name, config, self._managed_rules(config), containments
            )
        return True

    async def clear_client_dns_containments(self) -> int:
        async with self._rules_lock:
            app_name = await self._advanced_app_name()
            config = await self._get_app_config(app_name)
            containments = self._managed_containments(config)
            if not containments:
                return 0
            restored = config
            for containment in containments.values():
                client = containment.get("client")
                if isinstance(client, str):
                    restored = self._restore_previous_mapping(restored, client, containment)
            await self._set_managed_config(
                app_name, restored, self._managed_rules(restored), {}
            )
            return len(containments)

    def set_network_cidr(self, network_cidr: str) -> None:
        self.network_cidr = str(ip_network(network_cidr, strict=True))

    async def add_domain_rule(self, rule: DomainRuleRequest) -> bool:
        reference = self._direct_reference(rule)
        await self.upsert_managed_domain_rule(reference, rule)
        return True

    async def remove_domain_rule(self, rule: DomainRuleRequest) -> bool:
        return await self.remove_managed_domain_rule(self._direct_reference(rule))

    async def upsert_managed_domain_rule(self, reference: str, rule: DomainRuleRequest) -> str:
        self.require(
            DNSCapability.CLIENT_RULES if rule.client_identifiers else DNSCapability.DOMAIN_BLOCKING
        )
        normalized_reference = self._normalize_reference(reference)
        managed_rule = {
            "domain": normalize_domain(rule.domain),
            "allow": rule.allow,
            "clients": list(self._validated_clients(rule.client_identifiers)),
            "includeSubdomains": rule.include_subdomains,
        }
        async with self._rules_lock:
            app_name = await self._advanced_app_name()
            config = await self._get_app_config(app_name)
            state = self._managed_rules(config)
            state[normalized_reference] = managed_rule
            await self._set_managed_config(app_name, config, state)
        return f"technitium:{normalized_reference}"

    async def remove_managed_domain_rule(self, reference: str) -> bool:
        normalized_reference = self._normalize_reference(reference)
        async with self._rules_lock:
            app_name = await self._advanced_app_name()
            config = await self._get_app_config(app_name)
            state = self._managed_rules(config)
            if normalized_reference not in state:
                return False
            del state[normalized_reference]
            await self._set_managed_config(app_name, config, state)
        return True

    async def _installed_apps(self) -> list[dict[str, Any]]:
        response = (await self._request("GET", "/api/apps/list")).get("response")
        apps = response.get("apps") if isinstance(response, dict) else None
        if not isinstance(apps, list):
            raise TechnitiumProviderError("Technitium returned an invalid installed app list")
        return [app for app in apps if isinstance(app, dict)]

    @staticmethod
    def _query_logger(apps: list[dict[str, Any]]) -> tuple[str, str] | None:
        for app in apps:
            app_name = app.get("name")
            dns_apps = app.get("dnsApps")
            if not isinstance(app_name, str) or not isinstance(dns_apps, list):
                continue
            for dns_app in dns_apps:
                if (
                    isinstance(dns_app, dict)
                    and dns_app.get("isQueryLogger") is True
                    and isinstance(dns_app.get("classPath"), str)
                ):
                    return app_name, str(dns_app["classPath"])
        return None

    @staticmethod
    def _advanced_blocking_app(apps: list[dict[str, Any]]) -> str | None:
        for app in apps:
            name = app.get("name")
            if isinstance(name, str) and name.strip().lower() == "advanced blocking":
                return name
        return None

    @staticmethod
    def _store_app(
        apps: list[Any], predicate: Any
    ) -> dict[str, str] | None:
        for app in apps:
            if not isinstance(app, dict):
                continue
            name = app.get("name")
            url = app.get("url")
            if (
                isinstance(name, str)
                and isinstance(url, str)
                and url.startswith("https://")
                and predicate(name.strip().lower())
            ):
                return {"name": name, "url": url}
        return None

    async def _install_store_app(self, app: dict[str, str]) -> None:
        await self._request(
            "POST",
            "/api/apps/downloadAndInstall",
            data={"name": app["name"], "url": app["url"]},
        )

    async def _advanced_app_name(self) -> str:
        name = self._advanced_blocking_app(await self._installed_apps())
        if name is None:
            raise TechnitiumProviderError(
                "Technitium Advanced Blocking is not installed; save the integration "
                "to provision it."
            )
        return name

    async def _get_app_config(self, app_name: str) -> dict[str, Any]:
        response = (
            await self._request("GET", "/api/apps/config/get", params={"name": app_name})
        ).get("response")
        raw_config = response.get("config") if isinstance(response, dict) else None
        if raw_config in {None, ""}:
            return {}
        if not isinstance(raw_config, str):
            raise TechnitiumProviderError("Technitium returned an invalid app configuration")
        try:
            parsed = json.loads(raw_config)
        except json.JSONDecodeError as error:
            raise TechnitiumProviderError(
                "Technitium app configuration is not valid JSON"
            ) from error
        if not isinstance(parsed, dict):
            raise TechnitiumProviderError("Technitium app configuration must be a JSON object")
        return parsed

    async def _set_managed_config(
        self,
        app_name: str,
        existing: dict[str, Any],
        state: dict[str, dict[str, Any]],
        containments: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        config = self._render_config(
            existing,
            state,
            self._managed_containments(existing) if containments is None else containments,
        )
        await self._request(
            "POST",
            "/api/apps/config/set",
            params={"name": app_name},
            data={"config": json.dumps(config, indent=2, sort_keys=True)},
        )

    def _render_config(
        self,
        existing: dict[str, Any],
        state: dict[str, dict[str, Any]],
        containments: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        managed_containments = (
            self._managed_containments(existing) if containments is None else containments
        )
        config = dict(existing)
        config.update(
            {
                "enableBlocking": True,
                "blockingAnswerTtl": int(existing.get("blockingAnswerTtl", 30)),
                "blockListUrlUpdateIntervalHours": int(
                    existing.get("blockListUrlUpdateIntervalHours", 24)
                ),
                "blockListUrlUpdateIntervalMinutes": int(
                    existing.get("blockListUrlUpdateIntervalMinutes", 0)
                ),
                "localEndPointGroupMap": existing.get("localEndPointGroupMap", {}),
                _NETWATCH_RULES_KEY: state,
                _NETWATCH_CONTAINMENTS_KEY: managed_containments,
                "netwatchManagedConfigVersion": 1,
            }
        )
        existing_mappings = existing.get("networkGroupMap")
        mappings = {
            str(network): str(group)
            for network, group in (
                existing_mappings.items() if isinstance(existing_mappings, dict) else []
            )
            if not str(group).startswith(_NETWATCH_GROUP_PREFIX)
        }
        existing_groups = existing.get("groups")
        groups = [
            group
            for group in (existing_groups if isinstance(existing_groups, list) else [])
            if not (
                isinstance(group, dict)
                and str(group.get("name", "")).startswith(_NETWATCH_GROUP_PREFIX)
            )
        ]
        global_rules = [rule for rule in state.values() if not rule.get("clients")]
        by_client: dict[str, list[dict[str, Any]]] = {}
        for rule in state.values():
            clients = rule.get("clients")
            if not isinstance(clients, list):
                continue
            for client in clients:
                by_client.setdefault(str(client), []).append(rule)

        if global_rules:
            groups.append(self._group("netwatch-default", global_rules))
            for network in _PRIVATE_DNS_CLIENTS:
                mappings[network] = "netwatch-default"
        for client, client_rules in sorted(by_client.items()):
            group_name = f"netwatch-client-{client.replace('.', '-').replace(':', '-')}"
            mappings[client] = group_name
            groups.append(self._group(group_name, [*global_rules, *client_rules]))

        for containment in managed_containments.values():
            client = str(containment.get("client", ""))
            if not client:
                continue
            group_name = f"netwatch-containment-{client.replace('.', '-').replace(':', '-')}"
            mappings[client] = group_name
            groups.append(self._containment_group(group_name))

        config["networkGroupMap"] = mappings
        config["groups"] = groups
        return config

    @staticmethod
    def _group(name: str, rules: list[dict[str, Any]]) -> dict[str, Any]:
        allowed: set[str] = set()
        blocked: set[str] = set()
        allowed_regex: set[str] = set()
        blocked_regex: set[str] = set()
        for rule in rules:
            domain = str(rule["domain"])
            allow = bool(rule.get("allow"))
            include_subdomains = bool(rule.get("includeSubdomains", True))
            if include_subdomains:
                (allowed if allow else blocked).add(domain)
            else:
                pattern = rf"^{re.escape(domain)}\.?$"
                (allowed_regex if allow else blocked_regex).add(pattern)
        return {
            "name": name,
            "enableBlocking": True,
            "allowTxtBlockingReport": True,
            "blockAsNxDomain": True,
            "blockingAddresses": ["0.0.0.0", "::"],
            "allowed": sorted(allowed),
            "blocked": sorted(blocked),
            "allowListUrls": [],
            "blockListUrls": [],
            "allowedRegex": sorted(allowed_regex),
            "blockedRegex": sorted(blocked_regex),
            "regexAllowListUrls": [],
            "regexBlockListUrls": [],
            "adblockListUrls": [],
        }

    @staticmethod
    def _containment_group(name: str) -> dict[str, Any]:
        return {
            "name": name,
            "enableBlocking": True,
            "allowTxtBlockingReport": True,
            "blockAsNxDomain": True,
            "blockingAddresses": ["0.0.0.0", "::"],
            "allowed": [],
            "blocked": [],
            "allowListUrls": [],
            "blockListUrls": [],
            "allowedRegex": [],
            "blockedRegex": ["^.+$"],
            "regexAllowListUrls": [],
            "regexBlockListUrls": [],
            "adblockListUrls": [],
        }

    @staticmethod
    def _managed_rules(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
        raw = config.get(_NETWATCH_RULES_KEY)
        if not isinstance(raw, dict):
            return {}
        return {
            str(reference): dict(rule)
            for reference, rule in raw.items()
            if isinstance(reference, str) and isinstance(rule, dict)
        }

    @staticmethod
    def _managed_containments(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
        raw = config.get(_NETWATCH_CONTAINMENTS_KEY)
        if not isinstance(raw, dict):
            return {}
        return {
            str(reference): dict(value)
            for reference, value in raw.items()
            if isinstance(reference, str) and isinstance(value, dict)
        }

    @staticmethod
    def _containment_reference(client: str) -> str:
        return f"containment-{hashlib.sha256(client.encode()).hexdigest()[:24]}"

    @staticmethod
    def _restore_previous_mapping(
        config: dict[str, Any], client: str, containment: dict[str, Any]
    ) -> dict[str, Any]:
        restored = dict(config)
        raw_mappings = restored.get("networkGroupMap")
        mappings = dict(raw_mappings) if isinstance(raw_mappings, dict) else {}
        current = mappings.get(client)
        if isinstance(current, str) and current.startswith(_NETWATCH_GROUP_PREFIX):
            previous = containment.get("previousGroup")
            if isinstance(previous, str) and previous:
                mappings[client] = previous
            else:
                mappings.pop(client, None)
        restored["networkGroupMap"] = mappings
        return restored

    def _validated_clients(self, clients: tuple[str, ...]) -> tuple[str, ...]:
        network = ip_network(self.network_cidr)
        normalized: list[str] = []
        for value in clients:
            try:
                address = ip_address(value)
            except ValueError as error:
                raise ValueError("Client rule targets must be valid IP addresses") from error
            if address.version != 4 or not address.is_private or address not in network:
                raise ValueError("Client rule targets must belong to the authorized private subnet")
            normalized.append(str(address))
        return tuple(dict.fromkeys(sorted(normalized)))

    @staticmethod
    def _normalize_reference(reference: str) -> str:
        if not _MANAGED_REFERENCE_PATTERN.fullmatch(reference):
            raise ValueError("Managed rule reference is invalid")
        return reference.lower()

    @staticmethod
    def _direct_reference(rule: DomainRuleRequest) -> str:
        value = "|".join(
            (
                normalize_domain(rule.domain),
                str(rule.allow),
                ",".join(sorted(rule.client_identifiers)),
                str(rule.include_subdomains),
            )
        )
        return f"direct-{hashlib.sha256(value.encode()).hexdigest()[:24]}"

    @staticmethod
    def _parse_timestamp(value: object) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
        except ValueError:
            return None

    @staticmethod
    def _normalize_client(value: object) -> str:
        try:
            address = ip_address(str(value))
        except ValueError:
            return ""
        if address.version == 6 and address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(address)
