import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from database.session import database_is_ready, get_session
from schemas.readiness import ReadinessCheck, ReadinessResponse
from services.integrations import get_router_integration
from services.providers.common import ProviderStatus
from services.providers.dns import DNSCapability
from services.providers.registry import provider_registry
from services.scanner.service import configured_discovery_adapter

router = APIRouter(tags=["system"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
PROBE_TIMEOUT = 6.0
DISCOVERY_PROBE_TIMEOUT = 15.0


async def _probe(coro: object, fallback: str) -> tuple[ProviderStatus | None, str]:
    try:
        result = await asyncio.wait_for(coro, timeout=PROBE_TIMEOUT)  # type: ignore[arg-type]
        return result.status, result.message  # type: ignore[union-attr]
    except Exception:
        return ProviderStatus.DISCONNECTED, fallback


@router.get("/readiness", response_model=ReadinessResponse)
async def readiness(session: SessionDependency) -> ReadinessResponse:
    checks: dict[str, ReadinessCheck] = {}
    try:
        db_ready = await asyncio.wait_for(database_is_ready(), timeout=PROBE_TIMEOUT)
    except Exception:
        db_ready = False
    checks["database"] = ReadinessCheck(
        status="ready" if db_ready else "unavailable",
        message=(
            "Database connection is ready." if db_ready else "Database connection is unavailable."
        ),
    )

    adapter = None
    environment = None
    discovery_status = "ready"
    discovery_message = "Local discovery is available."
    try:
        adapter = configured_discovery_adapter()
        if settings.netwatch_host_sensor_url:
            environment = await asyncio.wait_for(
                adapter.detect_network(), timeout=DISCOVERY_PROBE_TIMEOUT
            )
            discovery_message = "Windows host sensor is reachable and returned network data."
        else:
            environment = await asyncio.wait_for(
                adapter.detect_network(), timeout=DISCOVERY_PROBE_TIMEOUT
            )
            discovery_message = "Container/system discovery is configured."
    except Exception:
        discovery_status = "unavailable"
        discovery_message = "Discovery or the configured Windows host sensor is unavailable."
    checks["discovery"] = ReadinessCheck(status=discovery_status, message=discovery_message)

    # A verified environment is required to attribute devices to the current LAN.
    identity_status = "ready"
    identity_message = f"Current network identity is {settings.netwatch_network_id}."
    try:
        if adapter is None:
            raise RuntimeError("discovery adapter is unavailable")
        if environment is None:
            identity_status = "degraded"
            identity_message = (
                "The configured network is available, but this deployment cannot verify the "
                "active interface automatically."
            )
        elif (
            environment.subnet != settings.netwatch_subnet
            or environment.network_id != settings.netwatch_network_id
        ):
            identity_status = "degraded"
            identity_message = "The detected network does not match the configured current network."
    except Exception:
        identity_status = "unavailable"
        identity_message = "Current network identity could not be read."
    checks["network_identity"] = ReadinessCheck(status=identity_status, message=identity_message)

    if not provider_registry.dns.supports(DNSCapability.QUERY_HISTORY):
        checks["technitium"] = ReadinessCheck(
            status="not_configured",
            message="Technitium is not configured with query-log support.",
        )
    else:
        provider_status, provider_message = await _probe(
            provider_registry.dns.test_connection(),
            "Technitium connectivity check timed out or failed.",
        )
        if provider_status != ProviderStatus.CONNECTED:
            checks["technitium"] = ReadinessCheck(status="unavailable", message=provider_message)
        else:
            try:
                await asyncio.wait_for(
                    provider_registry.dns.query_history(limit=1), timeout=PROBE_TIMEOUT
                )
                checks["technitium"] = ReadinessCheck(
                    status="ready",
                    message="Technitium connectivity and query log are ready.",
                )
            except Exception:
                checks["technitium"] = ReadinessCheck(
                    status="degraded",
                    message="Technitium is connected but its query log is not ready.",
                )

    if not db_ready:
        checks["router_control"] = ReadinessCheck(
            status="unavailable",
            message="Router capabilities cannot be checked while the database is unavailable.",
        )
    else:
        try:
            router = await asyncio.wait_for(get_router_integration(session), timeout=PROBE_TIMEOUT)
        except Exception:
            # The database check remains an independent signal; do not let a
            # metadata query turn readiness into an unstructured 500 response.
            router = None
        if router is not None and router.provider_id in {"nos", "hitron", "generic"}:
            checks["router_control"] = ReadinessCheck(
                status="unsupported",
                message="Router control is manual/unsupported for this router.",
            )
        else:
            router_status, router_message = await _probe(
                provider_registry.network.test_connection(),
                "Router control connectivity check timed out or failed.",
            )
            checks["router_control"] = ReadinessCheck(
                status=(
                    "ready"
                    if router_status == ProviderStatus.CONNECTED
                    and provider_registry.network.capabilities
                    else "not_configured"
                ),
                message=router_message,
            )

    # This endpoint is consumed by the setup UI. A degraded check is a valid
    # diagnostic result, not a failed HTTP request; deployment liveness remains
    # available through the separate /health endpoint.
    overall = "ready" if all(check.status == "ready" for check in checks.values()) else "degraded"
    return ReadinessResponse(status=overall, checks=checks)
