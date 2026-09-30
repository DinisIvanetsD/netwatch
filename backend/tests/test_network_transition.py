from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.config import settings
from models.device import DeviceSource
from services import network_transition as transition_module


class RecordingSession:
    def __init__(self) -> None:
        self.scan = SimpleNamespace(subnet="192.168.1.0/24", network_id="old-network")
        self.merged: dict[str, object] = {}
        self.commits = 0
        self.rollbacks = 0

    async def get(self, _model: object, _identifier: int) -> object:
        return self.scan

    async def merge(self, setting: object) -> None:
        self.merged[setting.key] = setting.value  # type: ignore[attr-defined]

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_same_cidr_physical_network_change_is_a_real_scope_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear = AsyncMock(return_value=2)
    reconcile = AsyncMock()
    broadcast = AsyncMock()
    update_scope = MagicMock()
    monkeypatch.setattr(transition_module, "clear_dns_containment_for_network_switch", clear)
    monkeypatch.setattr(transition_module, "reconcile_all_rules", reconcile)
    monkeypatch.setattr(transition_module.connection_manager, "broadcast", broadcast)
    monkeypatch.setattr(transition_module.provider_registry, "update_network_scope", update_scope)
    previous_subnet = settings.netwatch_subnet
    previous_network_id = settings.netwatch_network_id
    settings.netwatch_subnet = "192.168.1.0/24"
    settings.netwatch_network_id = "windows:00000000000000000000000000000000"
    session = RecordingSession()
    try:
        changed = await transition_module.transition_network(
            session,  # type: ignore[arg-type]
            subnet="192.168.1.0/24",
            network_id="windows:11111111111111111111111111111111",
            source=DeviceSource.LIVE,
            actor="scanner",
            scan_id=10,
            interface_name="Wi-Fi",
        )
    finally:
        settings.netwatch_subnet = previous_subnet
        settings.netwatch_network_id = previous_network_id

    assert changed is not None
    clear.assert_awaited_once_with(
        session,
        DeviceSource.LIVE,
        "192.168.1.0/24",
        "windows:00000000000000000000000000000000",
        actor="scanner",
    )
    assert session.merged == {
        "netwatch_subnet": "192.168.1.0/24",
        "netwatch_network_id": "windows:11111111111111111111111111111111",
    }
    assert session.scan.network_id == "windows:11111111111111111111111111111111"
    assert session.commits == 2
    reconcile.assert_awaited_once_with(session, DeviceSource.LIVE)
    update_scope.assert_called_once_with("192.168.1.0/24")
    broadcast.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconciliation_failure_is_reported_without_undoing_network_transition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear = AsyncMock(return_value=0)
    reconcile = AsyncMock(side_effect=RuntimeError("provider unavailable"))
    broadcast = AsyncMock()
    monkeypatch.setattr(transition_module, "clear_dns_containment_for_network_switch", clear)
    monkeypatch.setattr(transition_module, "reconcile_all_rules", reconcile)
    monkeypatch.setattr(transition_module.connection_manager, "broadcast", broadcast)
    monkeypatch.setattr(transition_module.provider_registry, "update_network_scope", MagicMock())
    previous_subnet = settings.netwatch_subnet
    previous_network_id = settings.netwatch_network_id
    settings.netwatch_subnet = "192.168.1.0/24"
    settings.netwatch_network_id = "old-network"
    session = RecordingSession()
    try:
        changed = await transition_module.transition_network(
            session,
            subnet="192.168.1.0/24",
            network_id="new-network",
            source=DeviceSource.LIVE,
            actor="scanner",
        )
    finally:
        settings.netwatch_subnet = previous_subnet
        settings.netwatch_network_id = previous_network_id

    assert changed is not None
    assert changed.reconciliation_succeeded is False
    assert changed.reconciliation_error == "provider unavailable"
    assert session.rollbacks == 1
    payload = broadcast.await_args.args[1]
    assert payload["reconciliation_succeeded"] is False
    assert payload["reconciliation_error"] == "provider unavailable"
