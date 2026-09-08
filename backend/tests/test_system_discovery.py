from ipaddress import ip_network

import pytest

from services.discovery.system import SystemDiscoveryAdapter


async def test_discovery_reports_missing_ping_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.discovery.system.shutil.which", lambda _: None)

    with pytest.raises(RuntimeError, match="ping command is not installed"):
        await SystemDiscoveryAdapter().discover(ip_network("192.168.1.0/30"))
