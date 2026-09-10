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


def test_production_rejects_wildcard_allowed_hosts() -> None:
    configured = Settings(netwatch_env="production", allowed_hosts="*")
    with pytest.raises(ValueError, match="cannot contain"):
        _ = configured.allowed_host_list


def test_rejects_invalid_technitium_dns_port() -> None:
    with pytest.raises(ValidationError, match="TECHNITIUM_DNS_PORT"):
        Settings(technitium_dns_port=70_000)


def test_accepts_only_loopback_or_docker_host_sensor_urls() -> None:
    configured = Settings(netwatch_host_sensor_url="http://host.docker.internal:8765")
    assert configured.netwatch_host_sensor_url == "http://host.docker.internal:8765"

    with pytest.raises(ValidationError, match="NETWATCH_HOST_SENSOR_URL"):
        Settings(netwatch_host_sensor_url="https://example.com:8765")


def test_host_sensor_is_opt_in_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NETWATCH_HOST_SENSOR_URL", raising=False)
    configured = Settings(_env_file=None)

    assert configured.netwatch_host_sensor_url is None
    assert configured.effective_host_sensor_token is None


def test_derives_a_separate_host_sensor_token() -> None:
    configured = Settings(netwatch_secret_key="test-secret")
    assert configured.effective_host_sensor_token
    assert configured.effective_host_sensor_token != "test-secret"
