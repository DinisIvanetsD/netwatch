import asyncio

import pytest

from services.scanner.coordinator import ScanCoordinator


@pytest.mark.asyncio
async def test_schedule_failure_releases_reservation(monkeypatch: pytest.MonkeyPatch) -> None:
    coordinator = ScanCoordinator()
    assert await coordinator.reserve() is True

    async def scan() -> None:
        return None

    def fail_create_task(_coroutine: object) -> asyncio.Task[None]:
        raise RuntimeError("scheduler unavailable")

    monkeypatch.setattr(asyncio, "create_task", fail_create_task)
    with pytest.raises(RuntimeError, match="scheduler unavailable"):
        coordinator.schedule(scan())

    assert coordinator.running is False
