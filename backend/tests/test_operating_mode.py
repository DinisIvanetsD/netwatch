from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from core.config import settings
from database.base import Base
from database.session import get_session
from main import app
from models.setting import AppSetting
from services.simulation import simulation_engine


@pytest.fixture
async def mode_client(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[TestClient, async_sessionmaker[AsyncSession], list[str]]]:
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    calls: list[str] = []

    async def skip_seed() -> None:
        calls.append("seed")

    def fake_start() -> None:
        calls.append("start")

    async def fake_stop() -> None:
        calls.append("stop")

    for name in (
        "seed_demo_devices",
        "seed_demo_history",
        "seed_demo_services",
        "seed_demo_internet_activity",
        "seed_demo_alerts",
    ):
        monkeypatch.setattr(f"api.routes.settings.{name}", skip_seed)
    monkeypatch.setattr(simulation_engine, "start", fake_start)
    monkeypatch.setattr(simulation_engine, "stop", fake_stop)
    monkeypatch.setattr(settings, "netwatch_demo_mode", False)

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            yield client, factory, calls
    finally:
        app.dependency_overrides.clear()


async def test_settings_report_the_live_operating_mode_by_default(
    mode_client: tuple[TestClient, async_sessionmaker[AsyncSession], list[str]],
) -> None:
    client, _, _ = mode_client

    response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json()["operating_mode"] == "live"


async def test_patch_switches_to_simulation_and_persists_the_mode(
    mode_client: tuple[TestClient, async_sessionmaker[AsyncSession], list[str]],
) -> None:
    client, factory, calls = mode_client

    response = client.patch("/api/settings", json={"operating_mode": "simulation"})

    assert response.status_code == 200
    assert response.json()["operating_mode"] == "simulation"
    assert settings.netwatch_demo_mode is True
    assert "seed" in calls
    assert "start" in calls
    async with factory() as session:
        record = await session.scalar(
            select(AppSetting).where(AppSetting.key == "netwatch_demo_mode")
        )
        assert record is not None
        assert record.value is True


async def test_patch_switches_back_to_live_and_stops_the_simulation(
    mode_client: tuple[TestClient, async_sessionmaker[AsyncSession], list[str]],
) -> None:
    client, _, calls = mode_client
    client.patch("/api/settings", json={"operating_mode": "simulation"})
    calls.clear()

    response = client.patch("/api/settings", json={"operating_mode": "live"})

    assert response.status_code == 200
    assert response.json()["operating_mode"] == "live"
    assert settings.netwatch_demo_mode is False
    assert "stop" in calls


async def test_patch_rejects_an_unknown_operating_mode(
    mode_client: tuple[TestClient, async_sessionmaker[AsyncSession], list[str]],
) -> None:
    client, _, _ = mode_client

    response = client.patch("/api/settings", json={"operating_mode": "demo"})

    assert response.status_code == 422
    assert settings.netwatch_demo_mode is False
