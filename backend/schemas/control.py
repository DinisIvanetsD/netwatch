from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from schemas.device import DeviceResponse
from services.control.constants import CONTENT_CATEGORIES
from services.providers.dns.adguard import normalize_domain


class RuleScope(StrEnum):
    GLOBAL = "global"
    PROFILE = "profile"
    DEVICE = "device"


class RuleAction(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"


class TrustState(StrEnum):
    TRUSTED = "trusted"
    UNKNOWN = "unknown"
    QUARANTINED = "quarantined"
    BLOCKED = "blocked"
    IGNORED = "ignored"


class InternetAccessState(StrEnum):
    ALLOWED = "allowed"
    PAUSED = "paused"
    BLOCKED = "blocked"


class DomainRuleCreate(BaseModel):
    scope_type: RuleScope
    scope_id: int | None = Field(default=None, ge=1)
    domain: str = Field(min_length=1, max_length=253)
    action: RuleAction
    include_subdomains: bool = True
    reason: str | None = Field(default=None, max_length=200)
    expires_at: datetime | None = None

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, value: str) -> str:
        return normalize_domain(value)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        return normalized or None

    @field_validator("expires_at")
    @classmethod
    def validate_expiry(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        aware = value if value.tzinfo else value.replace(tzinfo=UTC)
        if aware <= datetime.now(UTC):
            raise ValueError("Temporary rules must expire in the future")
        return aware

    @model_validator(mode="after")
    def validate_scope(self) -> "DomainRuleCreate":
        if self.scope_type == RuleScope.GLOBAL and self.scope_id is not None:
            raise ValueError("Global rules cannot have a scope ID")
        if self.scope_type != RuleScope.GLOBAL and self.scope_id is None:
            raise ValueError("Profile and device rules require a scope ID")
        if self.action == RuleAction.ALLOW and not self.include_subdomains:
            raise ValueError("Exact-domain allow rules are not supported")
        return self


class DomainRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scope_type: RuleScope
    scope_id: int | None
    domain: str
    action: RuleAction
    include_subdomains: bool
    reason: str | None
    enabled: bool
    expires_at: datetime | None
    enforcement_status: str
    enforcement_error: str | None
    last_applied_at: datetime | None
    created_at: datetime


class AccessScheduleInput(BaseModel):
    weekday: int = Field(ge=0, le=6)
    start_minute: int = Field(ge=0, le=1_439)
    end_minute: int = Field(ge=1, le=1_440)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_range(self) -> "AccessScheduleInput":
        if self.start_minute >= self.end_minute:
            raise ValueError("Schedule end must be later than its start")
        return self


class AccessScheduleResponse(AccessScheduleInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int


class ScheduleReplaceRequest(BaseModel):
    schedules: list[AccessScheduleInput] = Field(max_length=28)

    @field_validator("schedules")
    @classmethod
    def validate_no_overlaps(cls, value: list[AccessScheduleInput]) -> list[AccessScheduleInput]:
        by_day: dict[int, list[tuple[int, int]]] = {}
        for schedule in value:
            if schedule.enabled:
                by_day.setdefault(schedule.weekday, []).append(
                    (schedule.start_minute, schedule.end_minute)
                )
        for ranges in by_day.values():
            ordered = sorted(ranges)
            if any(
                current[0] < previous[1]
                for previous, current in zip(ordered, ordered[1:], strict=False)
            ):
                raise ValueError("Schedule ranges cannot overlap")
        return value


class ControlProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    internet_enabled: bool = True
    safe_search_enabled: bool = False
    blocked_categories: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Profile name cannot be empty")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        return normalized or None

    @field_validator("blocked_categories")
    @classmethod
    def validate_categories(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value))
        unknown = set(normalized).difference(CONTENT_CATEGORIES)
        if unknown:
            raise ValueError(f"Unknown content categories: {', '.join(sorted(unknown))}")
        return normalized


class ControlProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    internet_enabled: bool | None = None
    safe_search_enabled: bool | None = None
    blocked_categories: list[str] | None = Field(default=None, max_length=10)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Profile name cannot be empty")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        return normalized or None

    @field_validator("blocked_categories")
    @classmethod
    def validate_categories(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = list(dict.fromkeys(value))
        unknown = set(normalized).difference(CONTENT_CATEGORIES)
        if unknown:
            raise ValueError(f"Unknown content categories: {', '.join(sorted(unknown))}")
        return normalized


class ProfileDeviceAssignment(BaseModel):
    device_ids: list[int] = Field(default_factory=list, max_length=500)

    @field_validator("device_ids")
    @classmethod
    def normalize_ids(cls, value: list[int]) -> list[int]:
        if any(device_id < 1 for device_id in value):
            raise ValueError("Device IDs must be positive integers")
        return list(dict.fromkeys(value))


class ControlProfileResponse(BaseModel):
    id: int
    name: str
    description: str | None
    internet_enabled: bool
    safe_search_enabled: bool
    blocked_categories: list[str]
    created_at: datetime
    updated_at: datetime
    device_ids: list[int]
    device_count: int
    blocked_requests_today: int
    schedules: list[AccessScheduleResponse]
    domain_rules: list[DomainRuleResponse]
    schedule_state: str
    next_schedule_change: datetime | None


class ControlProfileListResponse(BaseModel):
    items: list[ControlProfileResponse]
    categories: dict[str, str]


class DeviceIdentityUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    device_type: str | None = Field(default=None, max_length=40)
    owner: str | None = Field(default=None, max_length=120)
    profile_id: int | None = Field(default=None, ge=1)

    @field_validator("name", "device_type", "owner")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        normalized = " ".join(value.split()) if value else None
        return normalized or None


class PauseInternetRequest(BaseModel):
    duration_minutes: int | None = Field(default=None, ge=1, le=10_080)


class DeviceControlResponse(BaseModel):
    changed: bool
    message: str
    device: DeviceResponse


class AccessAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int | None
    device_name: str | None = None
    action: str
    actor: str
    result: str
    provider_id: str | None
    message: str
    expires_at: datetime | None
    metadata: dict[str, object]
    created_at: datetime


class AccessAuditListResponse(BaseModel):
    items: list[AccessAuditResponse]
    total: int
    page: int
    per_page: int
    pages: int


class AccessOverviewResponse(BaseModel):
    devices: list[DeviceResponse]
    trusted: int
    unknown: int
    quarantined: int
    blocked: int
    ignored: int
    provider_id: str
    provider_name: str
    provider_configured: bool
    capabilities: dict[str, bool]
    message: str


class BlockedRequestResponse(BaseModel):
    id: int
    device_id: int
    device_name: str
    profile_id: int | None
    profile_name: str | None
    timestamp: datetime
    domain: str
    registered_domain: str | None
    service: str | None
    category: str
    rule: str
    provider_id: str
    explanation: str


class BlockedRequestListResponse(BaseModel):
    items: list[BlockedRequestResponse]
    total: int
    page: int
    per_page: int
    pages: int
