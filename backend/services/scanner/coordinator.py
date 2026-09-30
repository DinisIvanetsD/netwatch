import asyncio
from collections.abc import Coroutine
from typing import Any


class ScanCoordinator:
    def __init__(self) -> None:
        self._state_lock = asyncio.Lock()
        self._running = False
        self._tasks: set[asyncio.Task[Any]] = set()

    async def reserve(self) -> bool:
        async with self._state_lock:
            if self._running:
                return False
            self._running = True
            return True

    async def release(self) -> None:
        async with self._state_lock:
            self._running = False

    def schedule(self, coroutine: Coroutine[Any, Any, None]) -> None:
        try:
            task = asyncio.create_task(coroutine)
        except Exception:
            # The coroutine is created before this method is called.  If task
            # creation fails, close it and release the reservation immediately
            # so a failed scheduler cannot leave scans permanently blocked.
            coroutine.close()
            self._running = False
            raise
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self) -> None:
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self.release()

    @property
    def running(self) -> bool:
        return self._running


scan_coordinator = ScanCoordinator()
