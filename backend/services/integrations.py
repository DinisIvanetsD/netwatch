import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.credentials import CredentialCipher, CredentialConfigurationError
from database.session import SessionLocal
from models.integration import Integration
from services.providers.common import ProviderHealth, ProviderStatus
from services.providers.registry import provider_registry

logger = logging.getLogger(__name__)
ADGUARD_PROVIDER_ID = "adguard_home"


async def get_adguard_integration(session: AsyncSession) -> Integration | None:
    return await session.scalar(
        select(Integration).where(Integration.provider_id == ADGUARD_PROVIDER_ID)
    )


def _decrypt_password(integration: Integration) -> str:
    if not integration.encrypted_credentials:
        raise CredentialConfigurationError("AdGuard Home password is not configured")
    credentials = CredentialCipher(settings.netwatch_secret_key).decrypt(
        integration.encrypted_credentials
    )
    password = credentials.get("password")
    if not isinstance(password, str) or not password:
        raise CredentialConfigurationError("Stored AdGuard Home password is invalid")
    return password


async def activate_adguard(integration: Integration) -> ProviderHealth:
    if not integration.enabled:
        provider_registry.clear_dns()
        return ProviderHealth(ProviderStatus.NOT_CONFIGURED, "AdGuard Home is disabled.")
    try:
        password = _decrypt_password(integration)
        server_url = str(integration.configuration["server_url"])
        username = str(integration.configuration["username"])
    except (CredentialConfigurationError, KeyError) as error:
        provider_registry.clear_dns()
        return ProviderHealth(ProviderStatus.ERROR, str(error))
    provider_registry.configure_adguard(server_url, username, password)
    return await provider_registry.dns.test_connection()


async def save_adguard_integration(
    session: AsyncSession,
    *,
    server_url: str,
    username: str,
    password: str | None,
    enabled: bool,
) -> tuple[Integration, ProviderHealth]:
    integration = await get_adguard_integration(session)
    if integration is None:
        integration = Integration(
            provider_id=ADGUARD_PROVIDER_ID,
            display_name="AdGuard Home",
            kind="dns",
        )
        session.add(integration)
    if password:
        integration.encrypted_credentials = CredentialCipher(settings.netwatch_secret_key).encrypt(
            {"password": password}
        )
    elif not integration.encrypted_credentials:
        raise CredentialConfigurationError("A password is required for the first configuration")
    integration.configuration = {"server_url": server_url, "username": username}
    integration.enabled = enabled
    health = await activate_adguard(integration)
    integration.status = health.status.value
    integration.last_checked_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(integration)
    return integration, health


async def load_provider_integrations() -> None:
    async with SessionLocal() as session:
        integration = await get_adguard_integration(session)
        if integration is None:
            return
        health = await activate_adguard(integration)
        integration.status = health.status.value
        integration.last_checked_at = datetime.now(UTC)
        await session.commit()
        if health.status != ProviderStatus.CONNECTED:
            logger.warning("AdGuard Home integration unavailable: %s", health.message)
