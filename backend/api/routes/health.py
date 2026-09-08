from fastapi import APIRouter, Response, status

from core.config import settings
from database.session import database_is_ready
from schemas.health import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health_check(response: Response) -> HealthResponse:
    database_ready = await database_is_ready()
    if not database_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if database_ready else "degraded",
        service="netwatch-backend",
        database="ready" if database_ready else "unavailable",
        environment=settings.netwatch_env,
        demo_mode=settings.netwatch_demo_mode,
    )
