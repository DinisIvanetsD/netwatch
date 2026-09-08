from sqlalchemy import func, select

from core.config import settings
from database.session import SessionLocal
from models.control import AccessSchedule, ControlProfile
from models.device import DeviceSource
from models.setting import AppSetting


async def seed_default_control_profiles() -> None:
    source = DeviceSource.DEMO if settings.netwatch_demo_mode else DeviceSource.LIVE
    initialized_key = f"control_profiles_initialized_{source.value}"
    async with SessionLocal() as session:
        initialized = await session.get(AppSetting, initialized_key)
        if initialized is not None:
            return

        profile_count = int(
            (
                await session.scalar(
                    select(func.count())
                    .select_from(ControlProfile)
                    .where(ControlProfile.source == source)
                )
            )
            or 0
        )
        if profile_count:
            await session.merge(AppSetting(key=initialized_key, value=True))
            await session.commit()
            return

        adult = ControlProfile(
            name="Adult",
            source=source,
            description="Standard household access without profile-specific restrictions.",
            internet_enabled=True,
            safe_search_enabled=False,
            blocked_categories=[],
        )
        child = ControlProfile(
            name="Child",
            source=source,
            description="Age-appropriate defaults. Enforcement depends on provider capabilities.",
            internet_enabled=True,
            safe_search_enabled=True,
            blocked_categories=[
                "adult_content",
                "gambling",
                "malware",
                "phishing",
                "dating",
                "explicit_content",
            ],
        )
        guest = ControlProfile(
            name="Guest",
            source=source,
            description="Conservative policy for temporary household devices.",
            internet_enabled=True,
            safe_search_enabled=True,
            blocked_categories=["malware", "phishing", "advertising_trackers"],
        )
        session.add_all((adult, child, guest))
        await session.flush()
        session.add_all(
            AccessSchedule(
                profile_id=child.id,
                weekday=weekday,
                start_minute=7 * 60 if weekday < 5 else 8 * 60,
                end_minute=22 * 60 if weekday < 5 else 23 * 60 + 30,
                enabled=True,
            )
            for weekday in range(7)
        )
        await session.merge(AppSetting(key=initialized_key, value=True))
        await session.commit()
