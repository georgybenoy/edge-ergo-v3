"""OS-protected credential storage manager for EdgeErgo V3.

Security Guarantees:
- Secrets are stored exclusively in OS Credential Storage (Windows Credential Manager via keyring).
- Secrets are NEVER persisted to SQLite database files, plain JSON, INI, or logs.
- Memory lifecycle is transient; exceptions redact secret content.
- Atomic replacement on credential rotation.
"""

from __future__ import annotations

import logging
from typing import Protocol

import keyring
import keyring.errors

logger = logging.getLogger(__name__)

DEFAULT_SERVICE_NAME = "edge_ergo_device"


class CredentialStore(Protocol):
    """Protocol for secure on-device credential storage."""

    def store_credential(self, service: str, username: str, secret: str) -> None:
        """Stores or rotates a secret atomically."""
        ...

    def get_credential(self, service: str, username: str) -> str | None:
        """Retrieves the secret for the given service and username."""
        ...

    def delete_credential(self, service: str, username: str) -> bool:
        """Deletes the stored secret. Returns True if deleted or already absent."""
        ...


class KeyringCredentialStore:
    """Windows Credential Manager adapter using the keyring library."""

    def store_credential(self, service: str, username: str, secret: str) -> None:
        try:
            keyring.set_password(service, username, secret)
            logger.info("Successfully stored credential for public_id: %s in OS vault", username)
        except Exception as exc:
            # Explicitly suppress secret leakage in exception logging
            logger.error("Failed to store credential in OS vault: %s", type(exc).__name__)
            raise RuntimeError(
                f"Failed to securely store credential in OS Credential Manager: "
                f"{type(exc).__name__}"
            ) from None

    def get_credential(self, service: str, username: str) -> str | None:
        try:
            return keyring.get_password(service, username)
        except Exception as exc:
            logger.error("Failed to retrieve credential from OS vault: %s", type(exc).__name__)
            raise RuntimeError(
                f"Failed to read credential from OS Credential Manager: {type(exc).__name__}"
            ) from None

    def delete_credential(self, service: str, username: str) -> bool:
        try:
            keyring.delete_password(service, username)
            logger.info("Deleted credential for public_id: %s from OS vault", username)
            return True
        except keyring.errors.PasswordDeleteError:
            # Already deleted or not found
            return True
        except Exception as exc:
            logger.error("Failed to delete credential from OS vault: %s", type(exc).__name__)
            return False


class MemoryCredentialStore:
    """In-memory credential store for deterministic unit and integration tests."""

    def __init__(self) -> None:
        self._vault: dict[tuple[str, str], str] = {}

    def store_credential(self, service: str, username: str, secret: str) -> None:
        self._vault[(service, username)] = secret

    def get_credential(self, service: str, username: str) -> str | None:
        return self._vault.get((service, username))

    def delete_credential(self, service: str, username: str) -> bool:
        key = (service, username)
        if key in self._vault:
            del self._vault[key]
        return True


# Default global store instance (can be swapped for testing)
_GLOBAL_STORE: CredentialStore = KeyringCredentialStore()


def set_global_credential_store(store: CredentialStore) -> None:
    """Configures a custom CredentialStore (useful in tests)."""
    global _GLOBAL_STORE
    _GLOBAL_STORE = store


def get_global_credential_store() -> CredentialStore:
    """Returns the currently configured CredentialStore."""
    return _GLOBAL_STORE


def save_device_secret(
    public_id: str,
    secret: str,
    service: str = DEFAULT_SERVICE_NAME,
    store: CredentialStore | None = None,
) -> None:
    """Saves or atomically overwrites the device secret in secure OS storage."""
    active_store = store or _GLOBAL_STORE
    active_store.store_credential(service, public_id, secret)


def load_device_secret(
    public_id: str,
    service: str = DEFAULT_SERVICE_NAME,
    store: CredentialStore | None = None,
) -> str | None:
    """Loads the device secret from secure OS storage."""
    active_store = store or _GLOBAL_STORE
    return active_store.get_credential(service, public_id)


def delete_device_secret(
    public_id: str,
    service: str = DEFAULT_SERVICE_NAME,
    store: CredentialStore | None = None,
) -> bool:
    """Removes the device secret from secure OS storage."""
    active_store = store or _GLOBAL_STORE
    return active_store.delete_credential(service, public_id)
