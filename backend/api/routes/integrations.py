import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.credentials import CredentialConfigurationError
from database.session import get_session
from models.integration import Integration
from schemas.integration import (
    AdGuardConfigurationRequest,
    AdGuardTestRequest,
    IntegrationResponse,
    ProviderCapabilityListResponse,
    ProviderCapabilityResponse,
)
from services.integrations import (
    activate_adguard,
    get_adguard_integration,
    save_adguard_integration,
)
from services.providers.common import ProviderHealth
from services.providers.dns import AdGuardHomeProvider, DNSCapability
from services.providers.network import NetworkCapability
from services.providers.registry import ProviderKind, provider_registry

router = APIRouter(prefix="/integrations", tags=["integrations"])
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


def _integration_response(integration: Integration, health: ProviderHealth) -> IntegrationResponse:
    configuration = integration.configuration
    return IntegrationResponse(
        provider_id=integration.provider_id,
        display_name=integration.display_name,
        kind=ProviderKind.DNS,
        enabled=integration.enabled,
        server_url=str(configuration["server_url"]),
        username=str(configuration["username"]),
        password_set=bool(integration.encrypted_credentials),
        status=health.status,
        message=health.message,
        version=health.version,
    )


@router.get("/capabilities", response_model=ProviderCapabilityListResponse)
async def provider_capabilities() -> ProviderCapabilityListResponse:
    descriptors = provider_registry.descriptors()
    health_results = await asyncio.gather(
        provider_registry.dns.test_connection(),
        provider_registry.network.test_connection(),
    )
    capability_names = {
        ProviderKind.DNS: tuple(capability.value for capability in DNSCapability),
        ProviderKind.NETWORK: tuple(capability.value for capability in NetworkCapability),
    }
    return ProviderCapabilityListResponse(
        items=[
            ProviderCapabilityResponse(
                provider_id=descriptor.provider_id,
                display_name=descriptor.display_name,
                kind=descriptor.kind,
                configured=descriptor.configured,
                status=health.status,
                message=health.message,
                version=health.version,
                capabilities={
                    capability: capability in descriptor.capabilities
                    for capability in capability_names[descriptor.kind]
                },
            )
            for descriptor, health in zip(descriptors, health_results, strict=True)
        ]
    )


@router.get("/adguard", response_model=IntegrationResponse)
async def get_adguard(session: SessionDependency) -> IntegrationResponse:
    integration = await get_adguard_integration(session)
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="AdGuard Home is not configured."
        )
    health = await activate_adguard(integration)
    return _integration_response(integration, health)


@router.post("/adguard/test", response_model=ProviderCapabilityResponse)
async def test_adguard(payload: AdGuardTestRequest) -> ProviderCapabilityResponse:
    provider = AdGuardHomeProvider(payload.server_url, payload.username, payload.password)
    health = await provider.test_connection()
    return ProviderCapabilityResponse(
        provider_id=provider.provider_id,
        display_name=provider.display_name,
        kind=ProviderKind.DNS,
        configured=True,
        status=health.status,
        message=health.message,
        version=health.version,
        capabilities={
            capability.value: provider.supports(capability) for capability in DNSCapability
        },
    )


@router.put("/adguard", response_model=IntegrationResponse)
async def configure_adguard(
    payload: AdGuardConfigurationRequest, session: SessionDependency
) -> IntegrationResponse:
    try:
        integration, health = await save_adguard_integration(
            session,
            server_url=payload.server_url,
            username=payload.username,
            password=payload.password,
            enabled=payload.enabled,
        )
    except CredentialConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    return _integration_response(integration, health)


@router.delete("/adguard", status_code=status.HTTP_204_NO_CONTENT)
async def delete_adguard(session: SessionDependency) -> Response:
    integration = await get_adguard_integration(session)
    if integration is not None:
        await session.delete(integration)
        await session.commit()
    provider_registry.clear_dns()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
