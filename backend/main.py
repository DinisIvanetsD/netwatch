from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from api.router import api_router, websocket_router
from core.config import settings
from core.logging import configure_logging
from core.middleware import RequestSizeLimitMiddleware, SecurityHeadersMiddleware
from database.session import close_database
from services.demo import seed_demo_alerts, seed_demo_devices, seed_demo_history, seed_demo_services
from services.monitoring.engine import monitoring_engine
from services.scanner.coordinator import scan_coordinator
from services.settings import load_persisted_settings

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await load_persisted_settings()
    await seed_demo_devices()
    await seed_demo_history()
    await seed_demo_services()
    await seed_demo_alerts()
    if settings.monitoring_enabled:
        monitoring_engine.start()
    try:
        yield
    finally:
        await monitoring_engine.stop()
        await scan_coordinator.shutdown()
        await close_database()


app = FastAPI(
    title="NetWatch API",
    description="Local network monitoring and intelligence API for authorized private networks.",
    version="1.0.0",
    docs_url="/docs" if settings.netwatch_env != "production" else None,
    redoc_url="/redoc" if settings.netwatch_env != "production" else None,
    lifespan=lifespan,
)

app.add_middleware(
    SecurityHeadersMiddleware,
    production=settings.netwatch_env == "production",
)
app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_size_bytes)
if settings.netwatch_env == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)

app.include_router(api_router)
app.include_router(websocket_router)
