import asyncio
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import active_source
from core.credentials import CredentialConfigurationError
from database.session import get_session
from models.integration import Integration
from schemas.integration import (
    AdGuardConfigurationRequest,
    AdGuardTestRequest,
    IntegrationResponse,
    ProviderCapabilityListResponse,
    ProviderCapabilityResponse,
    SafeSearchConfiguration,
)
from services.control.rules import reconcile_all_rules
from services.integrations import (
    activate_adguard,
    get_adguard_integration,
    save_adguard_integration,
)
from services.providers.common import CapabilityUnavailableError, ProviderHealth, ProviderStatus
from services.providers.dns import (
    AdGuardHomeProvider,
    DNSCapability,
    SafeSearchSettings,
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
async def test_adguard(
    payload: AdGuardTestRequest, session: SessionDependency
) -> ProviderCapabilityResponse:
    if payload.password:
        provider = AdGuardHomeProvider(payload.server_url, payload.username, payload.password)
        health = await provider.test_connection()
    else:
        integration = await get_adguard_integration(session)
        if integration is None or not integration.encrypted_credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A password is required before testing this AdGuard Home connection.",
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
        health = await activate_adguard(integration)
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
    if health.status == ProviderStatus.CONNECTED:
        await reconcile_all_rules(session, active_source())
        await session.commit()
    return _integration_response(integration, health)


@router.delete("/adguard", status_code=status.HTTP_204_NO_CONTENT)
async def delete_adguard(session: SessionDependency) -> Response:
    integration = await get_adguard_integration(session)
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
