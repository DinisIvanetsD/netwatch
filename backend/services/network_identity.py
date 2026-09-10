from hashlib import sha256

from sqlalchemy import and_
from sqlalchemy.sql.elements import ColumnElement

from core.config import settings
from models.device import Device
from models.scan import Scan


def manual_network_id(subnet: str) -> str:
    """Return a stable, explicit fallback scope when no sensor identity is available."""

    digest = sha256(f"manual:{subnet}".encode()).hexdigest()[:24]
    return f"manual:{digest}"


def device_in_current_network() -> ColumnElement[bool]:
    return and_(
        Device.network_cidr == settings.netwatch_subnet,
        Device.network_id == settings.netwatch_network_id,
    )


def scan_in_current_network() -> ColumnElement[bool]:
    return and_(
        Scan.subnet == settings.netwatch_subnet,
        Scan.network_id == settings.netwatch_network_id,
    )
