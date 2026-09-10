import asyncio
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import active_source
from core.config import settings
from core.credentials import CredentialConfigurationError
from database.session import get_session
from models.integration import Integration
from schemas.integration import (
    IntegrationResponse,
    ProviderCapabilityListResponse,
    ProviderCapabilityResponse,
    RouterConfigurationRequest,
    RouterIntegrationResponse,
    SafeSearchConfiguration,
    TechnitiumConfigurationRequest,
    TechnitiumTestRequest,
)
from services.control.rules import reconcile_all_rules
from services.integrations import (
    activate_router,
    activate_technitium,
    get_router_integration,
    get_technitium_integration,
    save_router_integration,
    save_technitium_integration,
)
from services.providers.common import CapabilityUnavailableError, ProviderHealth, ProviderStatus
from services.providers.dns import (
    DNSCapability,
    SafeSearchSettings,
    TechnitiumDNSProvider,
)
from services.providers.network import NetworkCapability
from services.providers.registry import ProviderKind, provider_registry
from services.realtime.manager import connection_manager

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
        dns_port=int(configuration.get("dns_port", 53)),
        password_set=bool(integration.encrypted_credentials),
        status=health.status,
        message=health.message,
        version=health.version,
    )


def _router_response(integration: Integration, health: ProviderHealth) -> RouterIntegrationResponse:
    return RouterIntegrationResponse(
        provider_id=integration.provider_id,
        display_name=integration.display_name,
        kind=ProviderKind.NETWORK,
        enabled=integration.enabled,
        server_url=str(integration.configuration.get("server_url", "")),
        credential_set=bool(integration.encrypted_credentials),
        status=health.status,
        message=health.message,
        version=health.version,
    )


@router.get("/router", response_model=RouterIntegrationResponse)
async def get_router(session: SessionDependency) -> RouterIntegrationResponse:
    integration = await get_router_integration(session)
    if integration is None:
        raise HTTPException(status_code=404, detail="Router integration is not configured.")
    return _router_response(integration, await activate_router(integration))


@router.put("/router", response_model=RouterIntegrationResponse)
async def configure_router(
    payload: RouterConfigurationRequest, session: SessionDependency
) -> RouterIntegrationResponse:
    try:
        integration, health = await save_router_integration(session, **payload.model_dump())
    except (CredentialConfigurationError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _router_response(integration, health)


@router.delete("/router", status_code=status.HTTP_204_NO_CONTENT)
async def delete_router(session: SessionDependency) -> Response:
    integration = await get_router_integration(session)
    if integration is not None:
        await session.delete(integration)
        await session.commit()
    provider_registry.clear_network()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@router.get("/technitium", response_model=IntegrationResponse)
async def get_technitium(session: SessionDependency) -> IntegrationResponse:
    integration = await get_technitium_integration(session)
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Technitium DNS Server is not configured.",
        )
    health = await activate_technitium(integration)
    return _integration_response(integration, health)


@router.post("/technitium/test", response_model=ProviderCapabilityResponse)
async def test_technitium(
    payload: TechnitiumTestRequest, session: SessionDependency
) -> ProviderCapabilityResponse:
    if payload.password:
        provider = TechnitiumDNSProvider(
            payload.server_url,
            payload.username,
            payload.password,
            network_cidr=settings.netwatch_subnet,
        )
        health = await provider.test_connection()
    else:
        integration = await get_technitium_integration(session)
        if integration is None or not integration.encrypted_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A password is required before testing this Technitium connection.",
            )
        configuration = integration.configuration
        if (
            configuration.get("server_url") != payload.server_url
            or configuration.get("username") != payload.username
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Enter the password to test changed connection details.",
            )
        health = await activate_technitium(integration)
        provider = provider_registry.dns
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


@router.put("/technitium", response_model=IntegrationResponse)
async def configure_technitium(
    payload: TechnitiumConfigurationRequest, session: SessionDependency
) -> IntegrationResponse:
    try:
        integration, health = await save_technitium_integration(
            session,
            server_url=payload.server_url,
            username=payload.username,
            password=payload.password,
            dns_port=payload.dns_port,
            enabled=payload.enabled,
        )
    except CredentialConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    if health.status == ProviderStatus.CONNECTED:
        await reconcile_all_rules(session, active_source())
        await session.commit()
    return _integration_response(integration, health)


@router.delete("/technitium", status_code=status.HTTP_204_NO_CONTENT)
async def delete_technitium(session: SessionDependency) -> Response:
    integration = await get_technitium_integration(session)
    if integration is not None:
        await session.delete(integration)
        await session.commit()
    provider_registry.clear_dns()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/dns/safe-search", response_model=SafeSearchConfiguration)
async def get_safe_search() -> SafeSearchConfiguration:
    try:
        current = await provider_registry.dns.safe_search_status()
    except CapabilityUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The DNS provider could not return Safe Search settings.",
        ) from error
    return SafeSearchConfiguration(**asdict(current))


@router.put("/dns/safe-search", response_model=SafeSearchConfiguration)
async def update_safe_search(
    payload: SafeSearchConfiguration,
) -> SafeSearchConfiguration:
    try:
        updated = await provider_registry.dns.set_safe_search(
            SafeSearchSettings(**payload.model_dump())
        )
    except CapabilityUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The DNS provider could not update Safe Search settings.",
        ) from error
    await connection_manager.broadcast("provider.updated", {"provider_id": "dns"})
    return SafeSearchConfiguration(**asdict(updated))
