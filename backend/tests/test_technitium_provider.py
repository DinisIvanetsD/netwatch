import json
from datetime import UTC, datetime
from urllib.parse import parse_qs

import httpx
import pytest
from cryptography.fernet import Fernet

from core.credentials import CredentialCipher, CredentialConfigurationError
from services.providers.common import ProviderStatus
from services.providers.dns import DomainRuleRequest, TechnitiumDNSProvider, normalize_domain
from services.providers.validation import (
    ProviderURLValidationError,
    normalize_local_provider_url,
)


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


def _login_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "status": "ok",
            "token": "session-token",
            "info": {"version": "15.4.0"},
        },
    )


def _installed_apps(*, query_logger: bool = True, advanced: bool = True) -> list[dict]:
    apps: list[dict] = []
    if query_logger:
        apps.append(
            {
                "name": "Query Logs (Sqlite)",
                "dnsApps": [
                    {
                        "classPath": "QueryLogs.Sqlite.App",
                        "isQueryLogger": True,
                    }
                ],
            }
        )
    if advanced:
        apps.append({"name": "Advanced Blocking", "dnsApps": []})
    return apps


async def test_technitium_connection_and_query_log_parsing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/user/login":
            return _login_response()
        assert request.headers["Authorization"] == "Bearer session-token"
        if request.url.path == "/api/apps/list":
            return httpx.Response(
                200,
                json={"status": "ok", "response": {"apps": _installed_apps()}},
            )
        assert request.url.path == "/api/logs/query"
        assert request.url.params["entriesPerPage"] == "20"
        assert request.url.params["clientIpAddress"] == "192.168.1.25"
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "response": {
                    "entries": [
                        {
                            "timestamp": "2026-09-08T12:00:00Z",
                            "clientIpAddress": "192.168.1.25",
                            "responseType": "Blocked",
                            "rcode": "NxDomain",
                            "qname": "Example.COM.",
                            "qtype": "A",
                        },
                        {
                            "timestamp": "2026-09-08T12:00:01Z",
                            "clientIpAddress": "192.168.1.99",
                            "responseType": "Recursive",
                            "rcode": "NoError",
                            "qname": "ignored.test",
                            "qtype": "AAAA",
                        },
                    ]
                },
            },
        )

    async with _client(httpx.MockTransport(handler)) as client:
        provider = TechnitiumDNSProvider(
            "http://192.168.1.2:5380",
            "admin",
            "secret",
            network_cidr="192.168.1.0/24",
            client=client,
        )
        health = await provider.test_connection()
        records = await provider.query_history(limit=20, client="192.168.1.25")

    assert health.status == ProviderStatus.CONNECTED
    assert health.version == "15.4.0"
    assert len(records) == 1
    assert records[0].timestamp == datetime(2026, 9, 8, 12, tzinfo=UTC)
    assert records[0].domain == "example.com"
    assert records[0].blocked is True
    assert records[0].reason == "Blocked"


async def test_technitium_reports_authentication_failure_without_raising() -> None:
    transport = httpx.MockTransport(
        lambda _: httpx.Response(
            200,
            json={"status": "error", "errorMessage": "Invalid username or password"},
        )
    )
    async with _client(transport) as client:
        provider = TechnitiumDNSProvider(
            "http://127.0.0.1:5380",
            "bad",
            "bad",
            network_cidr="192.168.1.0/24",
            client=client,
        )
        health = await provider.test_connection()
    assert health.status == ProviderStatus.AUTHENTICATION_FAILED


async def test_technitium_provisions_required_apps_from_store() -> None:
    installed = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal installed
        if request.url.path == "/api/user/login":
            return _login_response()
        if request.url.path == "/api/apps/list":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "response": {
                        "apps": _installed_apps() if installed else [],
                    },
                },
            )
        if request.url.path == "/api/apps/listStoreApps":
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "response": {
                        "storeApps": [
                            {
                                "name": "Query Logs (Sqlite)",
                                "url": "https://download.technitium.com/query.zip",
                            },
                            {
                                "name": "Advanced Blocking",
                                "url": "https://download.technitium.com/blocking.zip",
                            },
                        ]
                    },
                },
            )
        if request.url.path == "/api/apps/downloadAndInstall":
            if parse_qs(request.content.decode()).get("name") == ["Advanced Blocking"]:
                installed = True
            return httpx.Response(200, json={"status": "ok", "response": {}})
        raise AssertionError(f"Unexpected request: {request.url}")

    async with _client(httpx.MockTransport(handler)) as client:
        provider = TechnitiumDNSProvider(
            "http://127.0.0.1:5380",
            "admin",
            "secret",
            network_cidr="192.168.1.0/24",
            client=client,
        )
        query_app, blocking_app = await provider.ensure_required_apps()

    assert query_app == "Query Logs (Sqlite)"
    assert blocking_app == "Advanced Blocking"


async def test_technitium_managed_rules_build_global_and_client_groups() -> None:
    config = {
        "enableBlocking": True,
        "networkGroupMap": {"192.168.50.0/24": "manual"},
        "groups": [{"name": "manual", "enableBlocking": False}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal config
        if request.url.path == "/api/user/login":
            return _login_response()
        if request.url.path == "/api/apps/list":
            return httpx.Response(
                200,
                json={"status": "ok", "response": {"apps": _installed_apps()}},
            )
        if request.url.path == "/api/apps/config/get":
            return httpx.Response(
                200,
                json={"status": "ok", "response": {"config": json.dumps(config)}},
            )
        if request.url.path == "/api/apps/config/set":
            config = json.loads(parse_qs(request.content.decode())["config"][0])
            return httpx.Response(200, json={"status": "ok", "response": {}})
        raise AssertionError(f"Unexpected request: {request.url}")

    async with _client(httpx.MockTransport(handler)) as client:
        provider = TechnitiumDNSProvider(
            "http://127.0.0.1:5380",
            "admin",
            "secret",
            network_cidr="192.168.1.0/24",
            client=client,
        )
        await provider.upsert_managed_domain_rule(
            "domain-rule-1",
            DomainRuleRequest(domain="global.example", allow=False),
        )
        await provider.upsert_managed_domain_rule(
            "domain-rule-2",
            DomainRuleRequest(
                domain="client.example",
                allow=False,
                clients=("192.168.1.25",),
            ),
        )

    groups = {group["name"]: group for group in config["groups"]}
    assert config["networkGroupMap"]["192.168.50.0/24"] == "manual"
    assert config["networkGroupMap"]["192.168.1.25"] == "netwatch-client-192-168-1-25"
    assert groups["manual"]["enableBlocking"] is False
    assert groups["netwatch-default"]["blocked"] == ["global.example"]
    assert groups["netwatch-client-192-168-1-25"]["blocked"] == [
        "client.example",
        "global.example",
    ]


async def test_technitium_removes_managed_rule_without_discarding_manual_groups() -> None:
    config: dict = {
        "networkGroupMap": {"192.168.50.0/24": "manual"},
        "groups": [{"name": "manual", "enableBlocking": False}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal config
        if request.url.path == "/api/user/login":
            return _login_response()
        if request.url.path == "/api/apps/list":
            return httpx.Response(
                200,
                json={"status": "ok", "response": {"apps": _installed_apps()}},
            )
        if request.url.path == "/api/apps/config/get":
            return httpx.Response(
                200,
                json={"status": "ok", "response": {"config": json.dumps(config)}},
            )
        config = json.loads(parse_qs(request.content.decode())["config"][0])
        return httpx.Response(200, json={"status": "ok", "response": {}})

    async with _client(httpx.MockTransport(handler)) as client:
        provider = TechnitiumDNSProvider(
            "http://127.0.0.1:5380",
            "admin",
            "secret",
            network_cidr="192.168.1.0/24",
            client=client,
        )
        await provider.upsert_managed_domain_rule(
            "domain-rule-7",
            DomainRuleRequest(domain="first.example", allow=False),
        )
        removed = await provider.remove_managed_domain_rule("domain-rule-7")

    assert removed is True
    assert config["networkGroupMap"] == {"192.168.50.0/24": "manual"}
    assert config["groups"] == [{"name": "manual", "enableBlocking": False}]


async def test_technitium_rejects_clients_outside_authorized_subnet() -> None:
    provider = TechnitiumDNSProvider(
        "http://127.0.0.1:5380",
        "admin",
        "secret",
        network_cidr="192.168.1.0/24",
    )
    with pytest.raises(ValueError, match="authorized private subnet"):
        provider._validated_clients(("8.8.8.8",))
    with pytest.raises(ValueError, match="authorized private subnet"):
        provider._validated_clients(("192.168.2.5",))


def test_bundled_technitium_preserves_unmanaged_configuration() -> None:
    provider = TechnitiumDNSProvider(
        "http://technitium:5380",
        "admin",
        "secret",
        network_cidr="192.168.1.0/24",
    )
    rendered = provider._render_config(
        {
            "localEndPointGroupMap": {"127.0.0.1": "bypass"},
            "networkGroupMap": {"0.0.0.0/0": "everyone else"},
            "groups": [{"name": "everyone else", "blocked": ["example.com"]}],
        },
        {
            "domain-rule-1": {
                "domain": "blocked.example",
                "allow": False,
                "clients": [],
                "includeSubdomains": True,
            }
        },
    )

    assert rendered["localEndPointGroupMap"] == {"127.0.0.1": "bypass"}
    assert rendered["networkGroupMap"]["0.0.0.0/0"] == "everyone else"
    assert {group["name"] for group in rendered["groups"]} == {
        "everyone else",
        "netwatch-default",
    }


def test_credentials_are_encrypted_and_invalid_keys_fail_closed() -> None:
    cipher = CredentialCipher(Fernet.generate_key().decode())
    token = cipher.encrypt({"password": "not-plain-text"})
    assert "not-plain-text" not in token
    assert cipher.decrypt(token) == {"password": "not-plain-text"}
    with pytest.raises(CredentialConfigurationError):
        CredentialCipher(None)


def test_provider_urls_and_domains_reject_public_or_malformed_targets() -> None:
    assert normalize_local_provider_url("HTTP://192.168.1.2:5380/") == "http://192.168.1.2:5380"
    assert normalize_domain("Example.COM.") == "example.com"
    with pytest.raises(ProviderURLValidationError):
        normalize_local_provider_url("https://example.com")
    with pytest.raises(ProviderURLValidationError):
        normalize_local_provider_url("http://127.0.0.1/api")
    with pytest.raises(ValueError):
        normalize_domain("not a domain")
