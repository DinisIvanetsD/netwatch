from unittest.mock import AsyncMock

import pytest

from services.providers.network import NetworkCapability, OpenWrtProvider, OPNsenseProvider
from services.providers.network.router import RouterProviderError, validate_router_url


def test_router_urls_are_strictly_local() -> None:
    assert validate_router_url("HTTP://192.168.1.1/") == "http://192.168.1.1"
    with pytest.raises(ValueError, match="local"):
        validate_router_url("https://router.example.com")
    with pytest.raises(ValueError, match="only a local"):
        validate_router_url("http://192.168.1.1/ui")


def test_router_capabilities_are_explicit_and_use_safe_identifiers() -> None:
    openwrt = OpenWrtProvider("http://127.0.0.1", "root", "secret")
    opnsense = OPNsenseProvider("http://127.0.0.1", "key", "secret")
    assert openwrt.identifier_kind == "mac"
    assert opnsense.identifier_kind == "ip"
    for provider in (openwrt, opnsense):
        assert provider.supports(NetworkCapability.FIREWALL_RULES)
        assert provider.supports(NetworkCapability.RELEASE_DEVICE)
        assert not provider.supports(NetworkCapability.QUARANTINE_DEVICE)


@pytest.mark.asyncio
async def test_openwrt_rule_reference_is_idempotent() -> None:
    provider = OpenWrtProvider("http://127.0.0.1", "root", "secret")
    provider._login = AsyncMock()  # type: ignore[method-assign]
    provider._call = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            {"values": [{".name": "cfg1", "name": "netwatch-aabbccddeeff"}]},
            {"code": 0},
        ]
    )

    result = await provider.block_internet("aa-bb-cc-dd-ee-ff")

    assert result.changed is False
    assert provider._call.await_args_list[0].args == (
        "uci",
        "get",
        {"config": "firewall", "type": "rule"},
    )
    assert provider._call.await_args_list[1].args == (
        "file",
        "exec",
        {"command": "/etc/init.d/firewall", "params": ["reload"], "env": {}},
    )


@pytest.mark.asyncio
async def test_openwrt_reenables_a_disabled_managed_rule() -> None:
    provider = OpenWrtProvider("http://127.0.0.1", "root", "secret")
    provider._login = AsyncMock()  # type: ignore[method-assign]
    provider._call = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            {"values": [{".name": "cfg1", "name": "netwatch-aabbccddeeff", "enabled": "0"}]},
            {},
            {},
            {"code": 0},
        ]
    )

    result = await provider.block_internet("aa-bb-cc-dd-ee-ff")

    assert result.changed is True
    assert provider._call.await_args_list[1].args == (
        "uci",
        "set",
        {
            "config": "firewall",
            "section": "cfg1",
            "values": {"enabled": "1"},
        },
    )
    assert provider._call.await_args_list[2].args == ("uci", "commit", {"config": "firewall"})


@pytest.mark.asyncio
async def test_openwrt_reads_indexed_uci_sections_and_releases_both_rules() -> None:
    provider = OpenWrtProvider("http://127.0.0.1", "root", "secret")
    provider._login = AsyncMock()  # type: ignore[method-assign]
    provider._call = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            {
                "values": {
                    "cfg-internet": {"name": "netwatch-aabbccddeeff"},
                    "cfg-device": {"name": "netwatch-aabbccddeeff-device"},
                }
            },
            {},
            {},
            {},
            {"code": 0},
        ]
    )

    result = await provider.release_device("aa:bb:cc:dd:ee:ff")

    assert result.changed is True
    assert provider._call.await_args_list[1].args == (
        "uci",
        "delete",
        {"config": "firewall", "section": "cfg-internet"},
    )
    assert provider._call.await_args_list[2].args == (
        "uci",
        "delete",
        {"config": "firewall", "section": "cfg-device"},
    )
    assert provider._call.await_args_list[3].args == ("uci", "commit", {"config": "firewall"})
    assert provider._call.await_args_list[4].args == (
        "file",
        "exec",
        {"command": "/etc/init.d/firewall", "params": ["reload"], "env": {}},
    )


@pytest.mark.asyncio
async def test_openwrt_block_device_is_explicitly_all_destinations_firewall_rule() -> None:
    provider = OpenWrtProvider("http://127.0.0.1", "root", "secret")
    provider._login = AsyncMock()  # type: ignore[method-assign]
    provider._call = AsyncMock(  # type: ignore[method-assign]
        side_effect=[{"values": []}, {}, {}, {"code": 0}]
    )

    result = await provider.block_device("aa:bb:cc:dd:ee:ff")

    assert result.changed is True
    add_values = provider._call.await_args_list[1].args[2]["values"]
    assert add_values["target"] == "DROP"
    assert "dest" not in add_values


@pytest.mark.asyncio
async def test_openwrt_successfully_reloads_firewall_after_commit() -> None:
    provider = OpenWrtProvider("http://127.0.0.1", "root", "secret")
    provider._login = AsyncMock()  # type: ignore[method-assign]
    provider._call = AsyncMock(  # type: ignore[method-assign]
        side_effect=[{"values": []}, {}, {}, {"code": 0}]
    )

    result = await provider.block_internet("aa:bb:cc:dd:ee:ff")

    assert result.changed is True
    assert provider._call.await_args_list[-1].args == (
        "file",
        "exec",
        {"command": "/etc/init.d/firewall", "params": ["reload"], "env": {}},
    )


@pytest.mark.asyncio
async def test_openwrt_fails_when_firewall_reload_is_rejected() -> None:
    provider = OpenWrtProvider("http://127.0.0.1", "root", "secret")
    provider._login = AsyncMock()  # type: ignore[method-assign]
    provider._call = AsyncMock(  # type: ignore[method-assign]
        side_effect=[{"values": []}, {}, {}, RouterProviderError("reload rejected")]
    )

    with pytest.raises(RouterProviderError, match="reload rejected"):
        await provider.block_internet("aa:bb:cc:dd:ee:ff")

    assert provider._call.await_args_list[-1].args == (
        "file",
        "exec",
        {"command": "/etc/init.d/firewall", "params": ["reload"], "env": {}},
    )


@pytest.mark.asyncio
async def test_openwrt_retries_firewall_reload_for_an_existing_rule() -> None:
    provider = OpenWrtProvider("http://127.0.0.1", "root", "secret")
    provider._login = AsyncMock()  # type: ignore[method-assign]
    provider._call = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            {"values": [{".name": "cfg1", "name": "netwatch-aabbccddeeff"}]},
            RouterProviderError("reload rejected"),
            {"values": [{".name": "cfg1", "name": "netwatch-aabbccddeeff"}]},
            {"code": 0},
        ]
    )

    with pytest.raises(RouterProviderError, match="reload rejected"):
        await provider.block_internet("aa:bb:cc:dd:ee:ff")

    result = await provider.block_internet("aa:bb:cc:dd:ee:ff")

    assert result.changed is False
    assert provider._call.await_args_list[1].args[0:2] == ("file", "exec")
    assert provider._call.await_args_list[3].args[0:2] == ("file", "exec")


@pytest.mark.asyncio
async def test_openwrt_release_is_idempotent_when_no_managed_rules_exist() -> None:
    provider = OpenWrtProvider("http://127.0.0.1", "root", "secret")
    provider._login = AsyncMock()  # type: ignore[method-assign]
    provider._call = AsyncMock(return_value={"values": []})  # type: ignore[method-assign]

    result = await provider.release_device("aa:bb:cc:dd:ee:ff")

    assert result.changed is False
    assert len(provider._call.await_args_list) == 1
    assert provider._call.await_args_list[0].args == (
        "uci",
        "get",
        {"config": "firewall", "type": "rule"},
    )


@pytest.mark.asyncio
async def test_openwrt_accepts_successful_ubus_response_without_payload(monkeypatch) -> None:
    provider = OpenWrtProvider("http://127.0.0.1", "root", "secret")
    request = AsyncMock(return_value={"jsonrpc": "2.0", "result": [0]})
    monkeypatch.setattr("services.providers.network.openwrt.request_json", request)

    assert await provider._call("uci", "commit", {"config": "firewall"}) == {}


@pytest.mark.asyncio
async def test_opnsense_rule_reference_is_idempotent() -> None:
    provider = OPNsenseProvider("http://127.0.0.1", "key", "secret")
    provider._request = AsyncMock(  # type: ignore[method-assign]
        return_value={"rows": [{"uuid": "rule-1", "description": "NetWatch 192.168.1.43"}]}
    )

    result = await provider.block_internet("192.168.1.43")

    assert result.changed is False
    provider._request.assert_awaited_once()


@pytest.mark.asyncio
async def test_opnsense_rejects_functional_add_failure_in_http_200_response() -> None:
    provider = OPNsenseProvider("http://127.0.0.1", "key", "secret")
    provider._request = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            {"rows": []},
            {"result": "failed", "message": "rule validation failed"},
        ]
    )

    with pytest.raises(RouterProviderError, match="rule validation failed"):
        await provider.block_internet("192.168.1.43")

    assert provider._request.await_count == 2


@pytest.mark.asyncio
async def test_opnsense_validates_delete_and_apply_responses() -> None:
    provider = OPNsenseProvider("http://127.0.0.1", "key", "secret")
    provider._request = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            {"rows": [{"uuid": "rule-1", "description": "NetWatch 192.168.1.43"}]},
            {"status": "success"},
            {"status": "failed", "message": "apply failed"},
        ]
    )

    with pytest.raises(RouterProviderError, match="apply failed"):
        await provider.unblock_internet("192.168.1.43")


def test_opnsense_rejects_non_private_or_malformed_identifiers() -> None:
    provider = OPNsenseProvider("http://127.0.0.1", "key", "secret")
    with pytest.raises(ValueError, match="private IPv4"):
        provider._validated_ip("8.8.8.8")
    with pytest.raises(ValueError, match="valid current IPv4"):
        provider._validated_ip("AA:BB:CC:DD:EE:FF")
