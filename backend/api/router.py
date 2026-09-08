from fastapi import APIRouter

from api.routes import alerts, devices, events, health, network, realtime, scans, services, settings

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(devices.router)
api_router.include_router(scans.router)
api_router.include_router(events.router)
api_router.include_router(services.router)
api_router.include_router(settings.router)
api_router.include_router(alerts.router)
api_router.include_router(network.router)

websocket_router = APIRouter()
websocket_router.include_router(realtime.router)
