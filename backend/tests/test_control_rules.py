from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models.control import DomainRule
from models.device import DeviceSource
from services.control.rules import enforce_domain_rule
from services.providers.registry import provider_registry


@pytest.mark.asyncio
async def test_scoped_rule_cleanup_retries_after_provider_failure(monkeypatch) -> None:
    provider = SimpleNamespace(
        remove_managed_domain_rule=AsyncMock(side_effect=[RuntimeError("offline"), True])
    )
    monkeypatch.setattr(provider_registry, "dns", provider)
    session = SimpleNamespace(scalar=AsyncMock(return_value=None))
    rule = DomainRule(
        id=7,
        source=DeviceSource.LIVE,
        scope_type="device",
        scope_id=42,
        domain="example.com",
        action="block",
        provider_reference="domain-rule-7",
        provider_rule="||example.com^",
        enforcement_status="active",
    )

    await enforce_domain_rule(session, rule, DeviceSource.LIVE)
    assert rule.enforcement_status == "error"
    assert rule.provider_reference == "domain-rule-7"

    await enforce_domain_rule(session, rule, DeviceSource.LIVE)
    assert rule.enforcement_status == "pending"
    assert rule.provider_reference is None
    assert rule.provider_rule is None
    assert provider.remove_managed_domain_rule.await_count == 2
