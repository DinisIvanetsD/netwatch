from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from models.control import AccessSchedule, ControlProfile


@dataclass(frozen=True, slots=True)
class ScheduleState:
    state: str
    next_change: datetime | None


def evaluate_schedule(
    profile: ControlProfile,
    schedules: list[AccessSchedule],
    *,
    now: datetime,
    timezone: str,
) -> ScheduleState:
    if not profile.internet_enabled:
        return ScheduleState("blocked_by_profile", None)
    enabled = [schedule for schedule in schedules if schedule.enabled]
    if not enabled:
        return ScheduleState("allowed", None)

    zone = ZoneInfo(timezone)
    local_now = now.astimezone(zone)

    def is_allowed(moment: datetime) -> bool:
        minute = moment.hour * 60 + moment.minute
        return any(
            schedule.weekday == moment.weekday()
            and schedule.start_minute <= minute < schedule.end_minute
            for schedule in enabled
        )

    allowed = is_allowed(local_now)

    boundaries: list[datetime] = []
    start_of_day = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    for day_offset in range(8):
        day = start_of_day + timedelta(days=day_offset)
        for schedule in enabled:
            if schedule.weekday != day.weekday():
                continue
            for minute in (schedule.start_minute, schedule.end_minute):
                boundary = day + timedelta(minutes=minute)
                if boundary > local_now:
                    boundaries.append(boundary)

    next_boundary = next(
        (boundary for boundary in sorted(set(boundaries)) if is_allowed(boundary) != allowed),
        None,
    )
    next_change = next_boundary.astimezone(UTC) if next_boundary else None
    return ScheduleState("allowed_by_schedule" if allowed else "blocked_by_schedule", next_change)
