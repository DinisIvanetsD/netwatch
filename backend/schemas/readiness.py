from typing import Literal

from pydantic import BaseModel

ReadinessStatus = Literal["ready", "degraded", "unavailable", "not_configured", "unsupported"]


class ReadinessCheck(BaseModel):
    status: ReadinessStatus
    message: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    checks: dict[str, ReadinessCheck]
