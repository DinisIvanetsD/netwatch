from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    service: str
    database: Literal["ready", "unavailable"]
    environment: str
    demo_mode: bool
