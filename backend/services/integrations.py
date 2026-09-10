import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.credentials import CredentialCipher, CredentialConfigurationError
from database.session import SessionLocal
from models.integration import Integration
from services.providers.common import ProviderHealth, ProviderStatus
from services.providers.dns import TechnitiumDNSProvider
from services.providers.network import OpenWrtProvider, OPNsenseProvider
from services.providers.registry import provider_registry

logger = logging.getLogger(__name__)
TECHNITIUM_PROVIDER_ID = "technitium_dns"
LEGACY_ADGUARD_PROVIDER_ID = "adguard_home"
ROUTER_PROVIDER_IDS = {"openwrt", "opnsense", "generic", "nos", "hitron"}


async def get_technitium_integration(session: AsyncSession) -> Integration | None:
    return await session.scalar(
        select(Integration).where(Integration.provider_id == TECHNITIUM_PROVIDER_ID)
    )


async def get_router_integration(session: AsyncSession) -> Integration | None:
    return await session.scalar(select(Integration).where(Integration.kind == "network"))


def _router_credentials(integration: Integration) -> dict[str, str]:
    if not integration.encrypted_credentials:
        raise CredentialConfigurationError("Router credentials are not configured")
    credentials = CredentialCipher(settings.netwatch_secret_key).decrypt(
        integration.encrypted_credentials
    )
    if not all(isinstance(credentials.get(key), str) and credentials[key] for key in credentials):
        raise CredentialConfigurationError("Stored router credentials are invalid")
    return credentials  # type: ignore[return-value]


async def activate_router(integration: Integration) -> ProviderHealth:
    if not integration.enabled:
        provider_registry.clear_network()
        return ProviderHealth(ProviderStatus.NOT_CONFIGURED, "Router integration is disabled.")
    if integration.provider_id in {"generic", "nos", "hitron"}:
        provider_registry.clear_network()
        return ProviderHealth(
            ProviderStatus.NOT_CONFIGURED,
            "This router has no supported automatic control API; use its manual controls.",
        )
    try:
        credentials = _router_credentials(integration)
        url = str(integration.configuration["server_url"])
        provider_id = integration.provider_id
        if provider_id == "openwrt":
            provider_registry.configure_network(
                OpenWrtProvider(url, credentials["username"], credentials["password"])
            )
        elif provider_id == "opnsense":
            provider_registry.configure_network(
                OPNsenseProvider(url, credentials["api_key"], credentials["api_secret"])
            )
    except (CredentialConfigurationError, KeyError) as error:
        provider_registry.clear_network()
        return ProviderHealth(ProviderStatus.ERROR, str(error))
    return await provider_registry.network.test_connection()


async def save_router_integration(
    session: AsyncSession,
    *,
    provider_id: str,
    server_url: str,
    username: str | None,
    password: str | None,
    api_key: str | None,
    api_secret: str | None,
    enabled: bool,
    confirm_state_changes: bool,
) -> tuple[Integration, ProviderHealth]:
    if provider_id not in ROUTER_PROVIDER_IDS:
        raise ValueError(
            "Unsupported router provider; choose OpenWrt, OPNsense, or manual fallback"
        )
    if enabled and provider_id in {"openwrt", "opnsense"} and not confirm_state_changes:
        raise ValueError(
            "Confirm that NetWatch may change router firewall state before enabling control"
        )
    integration = await get_router_integration(session)
    if integration is None or integration.provider_id != provider_id:
        if integration is not None:
            await session.delete(integration)
        integration = Integration(
            provider_id=provider_id,
            display_name={
                "openwrt": "OpenWrt",
                "opnsense": "OPNsense",
                "generic": "Generic / Manual",
                "nos": "NOS / Manual",
                "hitron": "Hitron / Manual",
            }[provider_id],
            kind="network",
        )
        session.add(integration)
    if provider_id == "openwrt":
        if username and password:
            integration.encrypted_credentials = CredentialCipher(
                settings.netwatch_secret_key
            ).encrypt({"username": username, "password": password})
        elif not integration.encrypted_credentials:
            raise CredentialConfigurationError(
                "Username and password are required for first OpenWrt configuration"
            )
    elif provider_id == "opnsense":
        if api_key and api_secret:
            integration.encrypted_credentials = CredentialCipher(
                settings.netwatch_secret_key
            ).encrypt({"api_key": api_key, "api_secret": api_secret})
        elif not integration.encrypted_credentials:
            raise CredentialConfigurationError(
                "API key and secret are required for first OPNsense configuration"
            )
    integration.configuration = {
        "server_url": server_url,
        "confirm_state_changes": confirm_state_changes,
    }
    integration.enabled = enabled
    health = await activate_router(integration)
    integration.status = health.status.value
    integration.last_checked_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(integration)
    return integration, health


def _decrypt_password(integration: Integration) -> str:
    if not integration.encrypted_credentials:
        raise CredentialConfigurationError("Technitium password is not configured")
    credentials = CredentialCipher(settings.netwatch_secret_key).decrypt(
        integration.encrypted_credentials
    )
    password = credentials.get("password")
    if not isinstance(password, str) or not password:
        raise CredentialConfigurationError("Stored Technitium password is invalid")
    return password


async def activate_technitium(integration: Integration) -> ProviderHealth:
    if not integration.enabled:
        provider_registry.clear_dns()
        return ProviderHealth(ProviderStatus.NOT_CONFIGURED, "Technitium DNS Server is disabled.")
    try:
        password = _decrypt_password(integration)
        server_url = str(integration.configuration["server_url"])
        username = str(integration.configuration["username"])
    except (CredentialConfigurationError, KeyError) as error:
        provider_registry.clear_dns()
        return ProviderHealth(ProviderStatus.ERROR, str(error))
    provider_registry.configure_technitium(
        server_url,
        username,
        password,
        network_cidr=settings.netwatch_subnet,
    )
    return await provider_registry.dns.test_connection()


async def _provision_required_apps(health: ProviderHealth) -> ProviderHealth:
    provider = provider_registry.dns
    if health.status != ProviderStatus.CONNECTED or not isinstance(provider, TechnitiumDNSProvider):
        return health
    try:
        await provider.ensure_required_apps()
    except Exception as error:
        logger.exception("Could not provision Technitium DNS apps")
        return ProviderHealth(
            ProviderStatus.ERROR,
            f"Technitium is connected, but required DNS apps could not be prepared: {error}",
            health.version,
        )
    return health


async def save_technitium_integration(
    session: AsyncSession,
    *,
    server_url: str,
    username: str,
    password: str | None,
    dns_port: int,
    enabled: bool,
) -> tuple[Integration, ProviderHealth]:
    integration = await get_technitium_integration(session)
    if integration is None:
        integration = Integration(
            provider_id=TECHNITIUM_PROVIDER_ID,
            display_name="Technitium DNS Server",
            kind="dns",
        )
        session.add(integration)
    if password:
        integration.encrypted_credentials = CredentialCipher(settings.netwatch_secret_key).encrypt(
            {"password": password}
        )
    elif not integration.encrypted_credentials:
        raise CredentialConfigurationError("A password is required for the first configuration")
    integration.configuration = {
        "server_url": server_url,
        "username": username,
        "dns_port": dns_port,
    }
    integration.enabled = enabled

    legacy = await session.scalar(
        select(Integration).where(Integration.provider_id == LEGACY_ADGUARD_PROVIDER_ID)
    )
    if legacy is not None:
        legacy.enabled = False
        legacy.status = ProviderStatus.NOT_CONFIGURED.value

    health = await activate_technitium(integration)
    health = await _provision_required_apps(health)
    integration.status = health.status.value
    integration.last_checked_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(integration)
    return integration, health


async def load_provider_integrations() -> None:
    async with SessionLocal() as session:
        router = await get_router_integration(session)
        if router is not None:
            health = await activate_router(router)
            router.status = health.status.value
            router.last_checked_at = datetime.now(UTC)
            await session.commit()
        integration = await get_technitium_integration(session)
        if integration is None and all(
            (
                settings.technitium_server_url,
                settings.technitium_username,
                settings.technitium_password,
            )
        ):
            try:
                await save_technitium_integration(
                    session,
                    server_url=str(settings.technitium_server_url),
                    username=settings.technitium_username,
                    password=settings.technitium_password,
                    dns_port=settings.technitium_dns_port,
                    enabled=True,
                )
            except Exception:
                logger.exception("Could not auto-configure Technitium DNS Server")
            return
        if integration is None:
            provider_registry.clear_dns()
            return
        health = await activate_technitium(integration)
        health = await _provision_required_apps(health)
        integration.status = health.status.value
        integration.last_checked_at = datetime.now(UTC)
        await session.commit()
        if health.status != ProviderStatus.CONNECTED:
            logger.warning("Technitium DNS integration unavailable: %s", health.message)
