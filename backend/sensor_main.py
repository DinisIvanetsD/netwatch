import asyncio
import platform
from hmac import compare_digest
from ipaddress import ip_network
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

from core.config import normalize_private_subnet, settings
from services.discovery.base import DiscoveryResult, NetworkEnvironment
from services.discovery.system import SystemDiscoveryAdapter
from services.discovery.windows import detect_windows_network, enrich_results_with_environment

app = FastAPI(
    title="NetWatch Windows Host Sensor",
    description="Loopback-only discovery sensor for the local Windows network.",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
bearer = HTTPBearer(auto_error=False)
scan_lock = asyncio.Lock()


class NetworkEnvironmentResponse(BaseModel):
    subnet: str
    local_ip: str
    gateway: str | None
    dns_servers: list[str]
    interface_name: str
    hostname: str | None
    mac_address: str | None
    network_id: str | None


class DiscoverRequest(BaseModel):
    subnet: str
    timeout_ms: int = Field(default=900, ge=100, le=5_000)
    concurrency: int = Field(default=32, ge=1, le=256)

    @field_validator("subnet")
    @classmethod
    def validate_subnet(cls, value: str) -> str:
        return normalize_private_subnet(value)


class DiscoveryResultResponse(BaseModel):
    ip_address: str
    reachable: bool
    latency_ms: float | None
    mac_address: str | None
    hostname: str | None
    method: str
    is_gateway: bool
    is_local: bool


class DiscoveryResponse(BaseModel):
    network: NetworkEnvironmentResponse
    devices: list[DiscoveryResultResponse]


def environment_response(environment: NetworkEnvironment) -> NetworkEnvironmentResponse:
    return NetworkEnvironmentResponse(
        subnet=environment.subnet,
        local_ip=environment.local_ip,
        gateway=environment.gateway,
        dns_servers=list(environment.dns_servers),
        interface_name=environment.interface_name,
        hostname=environment.hostname,
        mac_address=environment.mac_address,
        network_id=environment.network_id,
    )


def result_response(result: DiscoveryResult) -> DiscoveryResultResponse:
    return DiscoveryResultResponse(
        ip_address=result.ip_address,
        reachable=result.reachable,
        latency_ms=result.latency_ms,
        mac_address=result.mac_address,
        hostname=result.hostname,
        method=result.method,
        is_gateway=result.is_gateway,
        is_local=result.is_local,
    )


async def require_sensor_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    expected = settings.effective_host_sensor_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="NETWATCH_SECRET_KEY or NETWATCH_HOST_SENSOR_TOKEN is required.",
        )
    if credentials is None or not compare_digest(credentials.credentials, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid host sensor token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "status": "healthy",
        "platform": platform.system(),
        "authenticated": settings.effective_host_sensor_token is not None,
    }


@app.get(
    "/network",
    response_model=NetworkEnvironmentResponse,
    dependencies=[Depends(require_sensor_token)],
)
async def active_network() -> NetworkEnvironmentResponse:
    try:
        environment = await detect_windows_network()
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    return environment_response(environment)


@app.post(
    "/discover",
    response_model=DiscoveryResponse,
    dependencies=[Depends(require_sensor_token)],
)
async def discover(payload: DiscoverRequest) -> DiscoveryResponse:
    if scan_lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Windows host sensor scan is already running.",
        )
    async with scan_lock:
        # Keep the server deadline just inside the backend HTTP client's deadline;
        # this lets cancellation finish and releases scan_lock before the client gives up.
        try:
            async with asyncio.timeout(settings.host_sensor_timeout_seconds - 1):
                try:
                    environment = await detect_windows_network()
                except RuntimeError as error:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
                    ) from error
                requested_network = ip_network(payload.subnet)
                detected_network = ip_network(environment.subnet)
                if requested_network != detected_network:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            "The requested subnet is not the active Windows network. "
                            f"Detected {environment.subnet}."
                        ),
                    )
                adapter = SystemDiscoveryAdapter(
                    timeout_ms=payload.timeout_ms,
                    concurrency=payload.concurrency,
                )
                results = await adapter.discover(requested_network)
                results = enrich_results_with_environment(results, environment)
                return DiscoveryResponse(
                    network=environment_response(environment),
                    devices=[result_response(result) for result in results],
                )
        except TimeoutError as error:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Windows host sensor scan exceeded its server deadline.",
            ) from error
