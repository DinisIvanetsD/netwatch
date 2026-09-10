from typing import Literal

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


class TechnitiumConfigurationRequest(BaseModel):
    server_url: str
    username: str = Field(min_length=1, max_length=100)
    password: str | None = Field(default=None, min_length=1, max_length=500)
    dns_port: int = Field(default=53, ge=1, le=65_535)
    enabled: bool = True

    @field_validator("server_url")
    @classmethod
    def validate_server_url(cls, value: str) -> str:
        return normalize_local_provider_url(value)


class TechnitiumTestRequest(BaseModel):
    server_url: str
    username: str = Field(min_length=1, max_length=100)
    password: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("server_url")
    @classmethod
    def validate_server_url(cls, value: str) -> str:
        return normalize_local_provider_url(value)


class RouterConfigurationRequest(BaseModel):
    provider_id: Literal["openwrt", "opnsense", "generic", "nos", "hitron"]
    server_url: str = "http://192.168.1.1"
    username: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, max_length=500)
    api_key: str | None = Field(default=None, max_length=500)
    api_secret: str | None = Field(default=None, max_length=500)
    enabled: bool = True
    confirm_state_changes: bool = False

    @field_validator("server_url")
    @classmethod
    def validate_server_url(cls, value: str) -> str:
        return normalize_local_provider_url(value)


class RouterIntegrationResponse(BaseModel):
    provider_id: str
    display_name: str
    kind: ProviderKind
    enabled: bool
    server_url: str
    credential_set: bool
    status: ProviderStatus
    message: str
    version: str | None = None


class IntegrationResponse(BaseModel):
    provider_id: str
    display_name: str
    kind: ProviderKind
    enabled: bool
    server_url: str
    username: str
    dns_port: int
    password_set: bool
    status: ProviderStatus
    message: str
    version: str | None = None


class SafeSearchConfiguration(BaseModel):
    enabled: bool
    google: bool = True
    bing: bool = True
    youtube: bool = True
    duckduckgo: bool = True
    ecosia: bool = True
    pixabay: bool = True
    yandex: bool = True
