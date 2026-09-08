from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.alert import Alert
from models.event import Event
from models.metric import DeviceMetric
from models.scan import Scan


@dataclass(frozen=True, slots=True)
class RetentionResult:
    metrics_deleted: int
    events_deleted: int
    alerts_deleted: int
    scans_deleted: int


async def clear_historical_data(
    session: AsyncSession,
    *,
    older_than: datetime | None = None,
) -> RetentionResult:
    metric_query = delete(DeviceMetric)
    event_query = delete(Event)
    alert_query = delete(Alert)
    scan_query = delete(Scan)
    if older_than is not None:
        metric_query = metric_query.where(DeviceMetric.timestamp < older_than)
        event_query = event_query.where(Event.timestamp < older_than)
        alert_query = alert_query.where(Alert.created_at < older_than)
        scan_query = scan_query.where(Scan.created_at < older_than)

    alerts = await session.execute(alert_query)
    events = await session.execute(event_query)
    metrics = await session.execute(metric_query)
    scans = await session.execute(scan_query)
    return RetentionResult(
        metrics_deleted=metrics.rowcount or 0,
        events_deleted=events.rowcount or 0,
        alerts_deleted=alerts.rowcount or 0,
        scans_deleted=scans.rowcount or 0,
    )


async def prune_expired_history(session: AsyncSession, retention_days: int) -> RetentionResult:
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    return await clear_historical_data(session, older_than=cutoff)
