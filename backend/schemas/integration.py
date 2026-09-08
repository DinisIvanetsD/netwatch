from pydantic import BaseModel, Field, field_validator

from services.providers.common import ProviderStatus
from services.providers.registry import ProviderKind
from services.providers.validation import normalize_local_provider_url


class ProviderCapabilityResponse(BaseModel):
    provider_id: str
    display_name: str
    kind: ProviderKind
    configured: bool
    status: ProviderStatus
    message: str
    version: str | None = None
    capabilities: dict[str, bool]


class ProviderCapabilityListResponse(BaseModel):
    items: list[ProviderCapabilityResponse]


class AdGuardConfigurationRequest(BaseModel):
    server_url: str
    username: str = Field(min_length=1, max_length=100)
    password: str | None = Field(default=None, min_length=1, max_length=500)
    enabled: bool = True

    @field_validator("server_url")
    @classmethod
    def validate_server_url(cls, value: str) -> str:
        return normalize_local_provider_url(value)


class AdGuardTestRequest(BaseModel):
    server_url: str
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=500)

    @field_validator("server_url")
    @classmethod
    def validate_server_url(cls, value: str) -> str:
        return normalize_local_provider_url(value)


class IntegrationResponse(BaseModel):
    provider_id: str
    display_name: str
    kind: ProviderKind
    enabled: bool
    server_url: str
    username: str
    password_set: bool
    status: ProviderStatus
    message: str
    version: str | None = None
