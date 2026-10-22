"""Device enrollment flow for EdgeErgo V3.

Security Guarantees:
- Enrollment tokens and issued secrets are NEVER logged or written to plain text files.
- The issued credential is saved exclusively into Windows Credential Manager.
- Device identity (device_id, public_id, api_base_url) is committed transactionally to SQLite.
- Supports atomic re-enrollment and complete credential wiping via forget_device.
"""

from __future__ import annotations

import logging
import platform
from datetime import datetime, timezone

import httpx

from edge_ergo.storage.credentials import (
    CredentialStore,
    delete_device_secret,
    get_global_credential_store,
    save_device_secret,
)
from edge_ergo.storage.repository import StorageRepository
from edge_ergo.storage.types import DeviceIdentity
from edge_ergo.sync.client import validate_api_base_url

logger = logging.getLogger(__name__)


class EnrollmentError(Exception):
    """Base exception for enrollment failures."""

    def __init__(self, message: str, code: str = "ENROLLMENT_FAILED") -> None:
        super().__init__(message)
        self.code = code


class TokenInvalidOrExpiredError(EnrollmentError):
    """The enrollment token is invalid, expired, or was already consumed."""


class EnrollmentRateLimitError(EnrollmentError):
    """Enrollment requests throttled by server rate limiting."""


def enroll_device(
    api_base_url: str,
    token: str,
    label: str | None = None,
    credential_store: CredentialStore | None = None,
    repo: StorageRepository | None = None,
    http_client: httpx.Client | None = None,
) -> DeviceIdentity:
    """Performs cryptographic device enrollment against the hosted EdgeErgo API.

    1. Submits single-use enrollment token to POST /api/v1/devices/enroll
    2. Atomically stores issued credential in OS-protected storage (Windows Credential Manager)
    3. Persists non-secret device identity metadata in local SQLite
    """
    clean_url = validate_api_base_url(api_base_url)
    clean_token = token.strip()
    if not clean_token:
        raise EnrollmentError("Enrollment token cannot be empty.", "EMPTY_TOKEN")

    device_label = (label or f"{platform.node()} Workstation").strip()
    endpoint = f"{clean_url}/api/v1/devices/enroll"
    payload = {
        "token": clean_token,
        "label": device_label,
        "agent_version": "3.0.0",
    }

    client = http_client or httpx.Client(timeout=15.0, verify=True, follow_redirects=False)
    owns_client = http_client is None

    try:
        response = client.post(
            endpoint,
            json=payload,
            headers={
                "User-Agent": "EdgeErgo-Agent/3.0.0",
                "Content-Type": "application/json",
            },
        )
    except Exception as exc:
        logger.error("Connection failed during enrollment to %s: %s", endpoint, type(exc).__name__)
        raise EnrollmentError(
            f"Failed to connect to EdgeErgo server at '{clean_url}': {type(exc).__name__}",
            "CONNECTION_FAILED",
        ) from exc
    finally:
        if owns_client:
            client.close()

    if response.status_code in (200, 201):
        data = response.json()
        device_id = str(data["device_id"])
        public_id = str(data["public_id"])
        credential = str(data["credential"])  # eed_<public_id>.<secret>
        org_id = str(data["organization_id"])
        enrolled_label = str(data.get("label", device_label))
        now_utc = datetime.now(timezone.utc).isoformat()

        # 1. Store secret ONLY in OS-protected credential manager
        store = credential_store or get_global_credential_store()
        save_device_secret(public_id, credential, store=store)

        # 2. Store non-secret identity in SQLite
        identity = DeviceIdentity(
            device_id=device_id,
            public_id=public_id,
            api_base_url=clean_url,
            label=enrolled_label,
            organization_id=org_id,
            enrolled_at=now_utc,
        )

        if repo is not None:
            repo.save_device_identity(identity)

        logger.info(
            "Device enrollment succeeded for public_id: %s (label='%s')",
            public_id,
            enrolled_label,
        )
        return identity

    # Error handling
    err_msg = "Enrollment failed"
    err_code = "ENROLLMENT_FAILED"

    try:
        err_body = response.json()
        if "error" in err_body and isinstance(err_body["error"], dict):
            err_msg = err_body["error"].get("message", err_msg)
            err_code = err_body["error"].get("code", err_code)
    except Exception:
        pass

    if response.status_code in (400, 401, 404, 422):
        logger.warning("Enrollment token rejected: %s (code=%s)", err_msg, err_code)
        raise TokenInvalidOrExpiredError(
            f"Enrollment token is invalid, expired, or already used: {err_msg}",
            code=err_code,
        )

    if response.status_code == 429:
        logger.warning("Enrollment rate limited: %s", err_msg)
        raise EnrollmentRateLimitError(
            "Too many enrollment attempts. Please wait before retrying.",
            code="RATE_LIMITED",
        )

    raise EnrollmentError(
        f"Server error during enrollment (HTTP {response.status_code}): {err_msg}",
        code=err_code,
    )


def forget_device(
    credential_store: CredentialStore | None = None,
    repo: StorageRepository | None = None,
) -> bool:
    """Disassociates this workstation, deleting local identity and OS credential."""
    if repo is None:
        return False

    identity = repo.get_device_identity()
    if identity is None:
        logger.info("Device is not enrolled; nothing to forget.")
        return False

    store = credential_store or get_global_credential_store()
    delete_device_secret(identity.public_id, store=store)
    repo.delete_device_identity()
    logger.info("Successfully forgot device identity (public_id=%s)", identity.public_id)
    return True
