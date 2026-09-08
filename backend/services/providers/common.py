from dataclasses import dataclass
from enum import StrEnum


class ProviderStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    AUTHENTICATION_FAILED = "authentication_failed"
    UNSUPPORTED_VERSION = "unsupported_version"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    status: ProviderStatus
    message: str
    version: str | None = None


class CapabilityUnavailableError(RuntimeError):
    def __init__(self, provider_name: str, capability: StrEnum) -> None:
        self.provider_name = provider_name
        self.capability = capability
        super().__init__(
            f"{capability.value.replace('_', ' ').title()} is unavailable with {provider_name}."
        )
