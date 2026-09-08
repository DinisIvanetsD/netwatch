import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class CredentialConfigurationError(RuntimeError):
    pass


class CredentialCipher:
    def __init__(self, secret_key: str | None) -> None:
        if not secret_key:
            raise CredentialConfigurationError(
                "NETWATCH_SECRET_KEY must be configured before credentials can be saved"
            )
        try:
            self._fernet = Fernet(secret_key.encode())
        except (TypeError, ValueError) as error:
            raise CredentialConfigurationError(
                "NETWATCH_SECRET_KEY must be a valid Fernet key"
            ) from error

    def encrypt(self, credentials: dict[str, Any]) -> str:
        payload = json.dumps(credentials, separators=(",", ":")).encode()
        return self._fernet.encrypt(payload).decode()

    def decrypt(self, token: str) -> dict[str, Any]:
        try:
            value = json.loads(self._fernet.decrypt(token.encode()))
        except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CredentialConfigurationError(
                "Stored credentials could not be decrypted"
            ) from error
        if not isinstance(value, dict):
            raise CredentialConfigurationError("Stored credentials have an invalid format")
        return value
