from functools import lru_cache
from ipaddress import ip_network
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RFC1918_NETWORKS = tuple(
    ip_network(cidr) for cidr in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
)


def normalize_private_subnet(value: str) -> str:
    network = ip_network(value, strict=True)
    if network.version != 4:
        raise ValueError("NETWATCH_SUBNET must be an IPv4 network")
    if not any(network.subnet_of(private_network) for private_network in RFC1918_NETWORKS):
        raise ValueError("NETWATCH_SUBNET must be an RFC 1918 private network")
    if network.num_addresses > 65_536:
        raise ValueError("NETWATCH_SUBNET is too large; use /16 or smaller")
    if network.num_addresses < 4:
        raise ValueError("NETWATCH_SUBNET must provide at least two usable host addresses")
    return str(network)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    netwatch_env: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite+aiosqlite:///./data/netwatch.db"
    database_echo: bool = False
    netwatch_demo_mode: bool = False
    netwatch_subnet: str = "192.168.1.0/24"
    scan_interval: int = 60
    scan_concurrency: int = 32
    offline_after_missed_scans: int = 3
    monitoring_enabled: bool = True
    service_scan_enabled: bool = True
    service_ports: str = "22,53,80,443,445,3389"
    new_device_alerts: bool = True
    new_device_policy: Literal["allow", "allow_alert", "quarantine_alert", "block_alert"] = (
        "allow_alert"
    )
    device_offline_alerts: bool = True
    new_service_alerts: bool = True
    latency_alerts: bool = True
    retention_days: int = 30
    netwatch_timezone: str = "UTC"
    cors_origins: str = "http://localhost:3000"
    allowed_hosts: str = "localhost,127.0.0.1"
    max_request_size_bytes: int = 1_048_576
    netwatch_secret_key: str | None = None
    adguard_dns_port: int = 53

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith("sqlite:///"):
            return value.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("netwatch_subnet")
    @classmethod
    def validate_private_subnet(cls, value: str) -> str:
        return normalize_private_subnet(value)

    @field_validator("scan_interval")
    @classmethod
    def validate_scan_interval(cls, value: int) -> int:
        if not 10 <= value <= 86_400:
            raise ValueError("SCAN_INTERVAL must be between 10 and 86400 seconds")
        return value

    @field_validator("scan_concurrency")
    @classmethod
    def validate_scan_concurrency(cls, value: int) -> int:
        if not 1 <= value <= 256:
            raise ValueError("SCAN_CONCURRENCY must be between 1 and 256")
        return value

    @field_validator("offline_after_missed_scans")
    @classmethod
    def validate_offline_threshold(cls, value: int) -> int:
        if not 1 <= value <= 20:
            raise ValueError("OFFLINE_AFTER_MISSED_SCANS must be between 1 and 20")
        return value

    @field_validator("retention_days")
    @classmethod
    def validate_retention_days(cls, value: int) -> int:
        if not 1 <= value <= 3_650:
            raise ValueError("RETENTION_DAYS must be between 1 and 3650 days")
        return value

    @field_validator("adguard_dns_port")
    @classmethod
    def validate_adguard_dns_port(cls, value: int) -> int:
        if not 1 <= value <= 65_535:
            raise ValueError("ADGUARD_DNS_PORT must be a valid TCP/UDP port")
        return value

    @field_validator("netwatch_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("NETWATCH_TIMEZONE must be a valid IANA timezone") from error
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        hosts = [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]
        if not hosts:
            raise ValueError("ALLOWED_HOSTS must contain at least one hostname")
        if self.netwatch_env == "production" and "*" in hosts:
            raise ValueError("ALLOWED_HOSTS cannot contain '*' in production")
        return hosts

    @property
    def approved_service_ports(self) -> tuple[int, ...]:
        try:
            ports = tuple(
                dict.fromkeys(int(port.strip()) for port in self.service_ports.split(","))
            )
        except ValueError as error:
            raise ValueError("SERVICE_PORTS must be a comma-separated list of integers") from error
        if not ports or len(ports) > 64 or any(port < 1 or port > 65535 for port in ports):
            raise ValueError("SERVICE_PORTS must contain 1-64 valid TCP ports")
        return ports


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
