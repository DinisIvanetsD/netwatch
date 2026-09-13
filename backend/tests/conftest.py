import pytest

from core.config import settings


@pytest.fixture(autouse=True)
def isolate_runtime_settings(monkeypatch: pytest.MonkeyPatch):
    """Keep tests independent from the application's persisted runtime settings."""

    monkeypatch.setattr(settings, "netwatch_subnet", "192.168.1.0/24")
    monkeypatch.setattr(settings, "netwatch_network_id", "legacy")
    monkeypatch.setattr(settings, "monitoring_enabled", False)

    async def skip_persisted_settings_load() -> None:
        return None

    async def skip_provider_integrations() -> None:
        return None

    async def skip_startup_seed(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr("main.load_persisted_settings", skip_persisted_settings_load)
    monkeypatch.setattr("main.load_provider_integrations", skip_provider_integrations)
    monkeypatch.setattr("main.seed_default_control_profiles", skip_startup_seed)
    monkeypatch.setattr("main.reconcile_all_rules", skip_startup_seed)
    monkeypatch.setattr("main.seed_demo_devices", skip_startup_seed)
    monkeypatch.setattr("main.seed_demo_history", skip_startup_seed)
    monkeypatch.setattr("main.seed_demo_services", skip_startup_seed)
    monkeypatch.setattr("main.seed_demo_internet_activity", skip_startup_seed)
    monkeypatch.setattr("main.seed_demo_alerts", skip_startup_seed)
