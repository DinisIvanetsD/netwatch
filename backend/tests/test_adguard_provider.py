import json
from datetime import UTC, datetime

import httpx
import pytest
from cryptography.fernet import Fernet

from core.credentials import CredentialCipher, CredentialConfigurationError
from services.providers.common import ProviderStatus
from services.providers.dns import (
    AdGuardHomeProvider,
    DomainRuleRequest,
    SafeSearchSettings,
)
from services.providers.dns.adguard import normalize_domain
from services.providers.validation import (
    ProviderURLValidationError,
    normalize_local_provider_url,
)


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


async def test_adguard_connection_and_query_log_parsing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={"version": "v0.107.60", "running": True})
        assert request.url.params["limit"] == "20"
        assert request.url.params["search"] == "192.168.1.25"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "client": "192.168.1.25",
                        "question": {"name": "Example.COM.", "type": "A"},
                        "status": "NOERROR",
                        "reason": "FilteredBlackList",
                        "time": "2026-09-08T12:00:00Z",
                    },
                    {
                        "client": "192.168.1.99",
                        "question": {"name": "ignored.test", "type": "AAAA"},
                        "status": "NOERROR",
                        "reason": "NotFilteredNotFound",
                        "time": "2026-09-08T12:00:01Z",
                    },
                ]
            },
        )

    async with _client(httpx.MockTransport(handler)) as client:
        provider = AdGuardHomeProvider("http://192.168.1.2:3000", "admin", "secret", client=client)
        health = await provider.test_connection()
        records = await provider.query_history(limit=20, client="192.168.1.25")

    assert health.status == ProviderStatus.CONNECTED
    assert health.version == "v0.107.60"
    assert len(records) == 1
    assert records[0].timestamp == datetime(2026, 9, 8, 12, tzinfo=UTC)
    assert records[0].domain == "example.com"
    assert records[0].blocked is True


async def test_adguard_reports_authentication_failure_without_raising() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(401))
    async with _client(transport) as client:
        provider = AdGuardHomeProvider("http://127.0.0.1", "bad", "bad", client=client)
        health = await provider.test_connection()
    assert health.status == ProviderStatus.AUTHENTICATION_FAILED


async def test_adguard_updates_rules_without_discarding_existing_rules() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"user_rules": ["||existing.test^"]})
        return httpx.Response(200)

    async with _client(httpx.MockTransport(handler)) as client:
        provider = AdGuardHomeProvider("http://127.0.0.1", "admin", "secret", client=client)
        await provider.add_domain_rule(DomainRuleRequest(domain="Example.org", allow=False))

    assert requests[-1].url.path == "/control/filtering/set_rules"
    assert requests[-1].content == b'{"rules":["||existing.test^","||example.org^"]}'


async def test_adguard_accepts_empty_rules_from_new_installation() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"user_rules": None})
        return httpx.Response(200)

    async with _client(httpx.MockTransport(handler)) as client:
        provider = AdGuardHomeProvider("http://127.0.0.1", "admin", "secret", client=client)
        await provider.add_domain_rule(DomainRuleRequest(domain="first.example", allow=False))

    assert requests[-1].content == b'{"rules":["||first.example^"]}'


async def test_adguard_renders_private_client_rules_and_rejects_public_clients() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"user_rules": []})
        return httpx.Response(200)

    async with _client(httpx.MockTransport(handler)) as client:
        provider = AdGuardHomeProvider("http://127.0.0.1", "admin", "secret", client=client)
        await provider.add_domain_rule(
            DomainRuleRequest(
                domain="example.org",
                allow=False,
                clients=("192.168.1.25", "10.0.0.8"),
            )
        )
        with pytest.raises(ValueError, match="local IP"):
            await provider.add_domain_rule(
                DomainRuleRequest(
                    domain="example.org",
                    allow=False,
                    clients=("8.8.8.8",),
                )
            )

    assert requests[1].content == b'{"rules":["||example.org^$client=10.0.0.8|192.168.1.25"]}'


async def test_adguard_managed_rule_update_and_removal_preserves_manual_rules() -> None:
    rules = ["||manual.example^"]

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal rules
        if request.method == "GET":
            return httpx.Response(200, json={"user_rules": rules})
        rules = list(json.loads(request.content)["rules"])
        return httpx.Response(200)

    async with _client(httpx.MockTransport(handler)) as client:
        provider = AdGuardHomeProvider("http://127.0.0.1", "admin", "secret", client=client)
        await provider.upsert_managed_domain_rule(
            "domain-rule-7",
            DomainRuleRequest(domain="first.example", allow=False),
        )
        await provider.upsert_managed_domain_rule(
            "domain-rule-7",
            DomainRuleRequest(domain="second.example", allow=False),
        )
        removed = await provider.remove_managed_domain_rule("domain-rule-7")

    assert removed is True
    assert rules == ["||manual.example^"]


async def test_adguard_reads_and_updates_safe_search() -> None:
    put_payload: dict[str, bool] | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal put_payload
        if request.method == "PUT":
            put_payload = json.loads(request.content)
            return httpx.Response(200)
        return httpx.Response(
            200,
            json={
                "enabled": True,
                "google": True,
                "bing": True,
                "youtube": True,
                "duckduckgo": False,
                "ecosia": False,
                "pixabay": False,
                "yandex": False,
            },
        )

    requested = SafeSearchSettings(
        enabled=True,
        google=True,
        bing=True,
        youtube=True,
        duckduckgo=False,
        ecosia=False,
        pixabay=False,
        yandex=False,
    )
    async with _client(httpx.MockTransport(handler)) as client:
        provider = AdGuardHomeProvider("http://127.0.0.1", "admin", "secret", client=client)
        result = await provider.set_safe_search(requested)

    assert put_payload == {
        "enabled": True,
        "google": True,
        "bing": True,
        "youtube": True,
        "duckduckgo": False,
        "ecosia": False,
        "pixabay": False,
        "yandex": False,
    }
    assert result == requested


def test_credentials_are_encrypted_and_invalid_keys_fail_closed() -> None:
    cipher = CredentialCipher(Fernet.generate_key().decode())
    token = cipher.encrypt({"password": "not-plain-text"})
    assert "not-plain-text" not in token
    assert cipher.decrypt(token) == {"password": "not-plain-text"}
    with pytest.raises(CredentialConfigurationError):
        CredentialCipher(None)


def test_provider_urls_and_domains_reject_public_or_malformed_targets() -> None:
    assert normalize_local_provider_url("HTTP://192.168.1.2:3000/") == "http://192.168.1.2:3000"
    assert normalize_domain("Example.COM.") == "example.com"
    with pytest.raises(ProviderURLValidationError):
        normalize_local_provider_url("https://example.com")
    with pytest.raises(ProviderURLValidationError):
        normalize_local_provider_url("http://127.0.0.1/control")
    with pytest.raises(ValueError):
        normalize_domain("not a domain")
