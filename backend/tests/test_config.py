import pytest
from pydantic import ValidationError

from core.config import Settings


def test_accepts_private_subnet() -> None:
    configured = Settings(netwatch_subnet="10.42.0.0/24")
    assert configured.netwatch_subnet == "10.42.0.0/24"


@pytest.mark.parametrize(
    "subnet",
    [
        "8.8.8.0/24",
        "127.0.0.0/24",
        "169.254.0.0/16",
        "192.0.2.0/24",
        "192.168.1.1/24",
        "not-a-subnet",
    ],
)
def test_rejects_invalid_or_public_subnet(subnet: str) -> None:
    with pytest.raises((ValidationError, ValueError)):
        Settings(netwatch_subnet=subnet)


def test_normalizes_sqlite_url_for_async_driver() -> None:
    configured = Settings(database_url="sqlite:///./test.db")
    assert configured.database_url == "sqlite+aiosqlite:///./test.db"


def test_approved_service_ports_are_validated_and_deduplicated() -> None:
    configured = Settings(service_ports="22,443,22")
    assert configured.approved_service_ports == (22, 443)

    with pytest.raises(ValueError, match="valid TCP ports"):
        _ = Settings(service_ports="0").approved_service_ports
