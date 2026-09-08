from core.config import settings
from models.device import DeviceSource


def active_source() -> DeviceSource:
    return DeviceSource.DEMO if settings.netwatch_demo_mode else DeviceSource.LIVE
