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
from services.providers.registry import provider_registry

logger = logging.getLogger(__name__)
TECHNITIUM_PROVIDER_ID = "technitium_dns"
LEGACY_ADGUARD_PROVIDER_ID = "adguard_home"


async def get_technitium_integration(session: AsyncSession) -> Integration | None:
    return await session.scalar(
        select(Integration).where(Integration.provider_id == TECHNITIUM_PROVIDER_ID)
    )


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
    if health.status != ProviderStatus.CONNECTED or not isinstance(
        provider, TechnitiumDNSProvider
    ):
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
