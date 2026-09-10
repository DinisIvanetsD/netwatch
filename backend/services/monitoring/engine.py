import asyncio
import logging
from datetime import UTC, datetime

from core.config import settings
from database.session import SessionLocal
from models.device import DeviceSource
from models.scan import Scan, ScanStatus
from services.scanner.coordinator import scan_coordinator
from services.scanner.service import scan_service

logger = logging.getLogger(__name__)


class MonitoringEngine:
    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="netwatch-monitor")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(settings.scan_interval)
            try:
                await self._schedule_scan()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Could not schedule the next monitoring scan")

    async def _schedule_scan(self) -> None:
        if not await scan_coordinator.reserve():
            logger.info("Skipping scheduled scan because another scan is running")
            return
        try:
            async with SessionLocal() as session:
                scan = Scan(
                    status=ScanStatus.PENDING,
                    subnet=settings.netwatch_subnet,
                    network_id=settings.netwatch_network_id,
                    source=DeviceSource.DEMO if settings.netwatch_demo_mode else DeviceSource.LIVE,
                    created_at=datetime.now(UTC),
                )
                session.add(scan)
                await session.commit()
                await session.refresh(scan)
            scan_coordinator.schedule(scan_service.run(scan.id))
        except Exception:
            await scan_coordinator.release()
            raise


monitoring_engine = MonitoringEngine()
