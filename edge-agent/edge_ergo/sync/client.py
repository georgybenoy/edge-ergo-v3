"""HTTP Client for EdgeErgo telemetry ingestion and device heartbeats."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class SyncClientError(Exception):
    """Base exception for synchronization client errors."""


class TransientNetworkError(SyncClientError):
    """Temporary network, connectivity, or server 5xx error eligible for backoff retry."""


class RateLimitedError(TransientNetworkError):
    """Server returned 429 Rate Limited, potentially with a Retry-After header."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class DeviceAuthError(SyncClientError):
    """Server returned 401 or 403: Device is unauthorized, token invalid, or revoked."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


class PermanentPayloadError(SyncClientError):
    """Server rejected payload with 400, 413, or 422 (malformed or unprocessable)."""


@dataclass(frozen=True)
class EventResultItem:
    event_id: str
    status: str  # 'accepted', 'duplicate', 'rejected'
    reason_code: str | None = None


@dataclass(frozen=True)
class BatchUploadResult:
    results: list[EventResultItem]
    total_accepted: int
    total_duplicates: int
    total_rejected: int


def validate_api_base_url(url: str, allow_insecure_localhost: bool = True) -> str:
    """Validates that API URL enforces HTTPS, allowing HTTP only for local development."""
    cleaned = url.strip().rstrip("/")
    parsed = urlparse(cleaned)

    if parsed.scheme == "https":
        return cleaned

    if parsed.scheme == "http":
        host = (parsed.hostname or "").lower()
        if allow_insecure_localhost and host in ("localhost", "127.0.0.1", "::1", "testserver"):
            return cleaned
        raise ValueError(
            f"Insecure HTTP connection is strictly forbidden for remote host '{host}'. "
            "EdgeErgo requires HTTPS for all production communication."
        )

    raise ValueError(f"Invalid URL scheme '{parsed.scheme}'. EdgeErgo requires HTTPS.")


class SyncClient:
    """Robust, TLS-verified HTTP client communicating with EdgeErgo API."""

    def __init__(
        self,
        api_base_url: str,
        credential: str,
        http_client: httpx.Client | None = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.api_base_url = validate_api_base_url(api_base_url)
        self._credential = credential
        self._timeout = timeout_seconds

        # Configure or adopt httpx.Client
        if http_client is not None:
            self._client = http_client
            self._owns_client = False
        else:
            self._client = httpx.Client(
                timeout=httpx.Timeout(timeout_seconds, connect=5.0),
                verify=True,
                follow_redirects=False,
            )
            self._owns_client = True

    @property
    def auth_headers(self) -> dict[str, str]:
        """Generates standard authorization headers. Credential is never logged."""
        return {
            "Authorization": f"Bearer {self._credential}",
            "User-Agent": "EdgeErgo-Agent/3.0.0",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def upload_batch(self, payload: dict[str, Any]) -> BatchUploadResult:
        """Sends a batch of telemetry events to POST /api/v1/assessments/batch."""
        endpoint = f"{self.api_base_url}/api/v1/assessments/batch"

        try:
            response = self._client.post(
                endpoint,
                json=payload,
                headers=self.auth_headers,
            )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning(
                "Transient network error connecting to %s: %s", endpoint, type(exc).__name__
            )
            raise TransientNetworkError(f"Network error: {type(exc).__name__}") from exc
        except Exception as exc:
            logger.error("Unexpected client error during batch upload: %s", exc)
            raise TransientNetworkError(f"Transport error: {exc}") from exc

        # Handle HTTP status codes
        if response.status_code == 200:
            data = response.json()
            raw_results = data.get("results", [])
            items = [
                EventResultItem(
                    event_id=str(r["event_id"]),
                    status=str(r["status"]),
                    reason_code=r.get("reason_code"),
                )
                for r in raw_results
            ]
            return BatchUploadResult(
                results=items,
                total_accepted=int(data.get("total_accepted", 0)),
                total_duplicates=int(data.get("total_duplicates", 0)),
                total_rejected=int(data.get("total_rejected", 0)),
            )

        if response.status_code in (401, 403):
            logger.error("Authentication rejected by server (HTTP %d)", response.status_code)
            raise DeviceAuthError(
                "Device credential unauthorized, expired, or revoked by server.",
                status_code=response.status_code,
            )

        if response.status_code == 429:
            retry_after_hdr = response.headers.get("Retry-After")
            retry_after_val: float | None = None
            if retry_after_hdr:
                try:
                    retry_after_val = float(retry_after_hdr)
                except ValueError:
                    pass
            logger.warning("Rate limit exceeded (HTTP 429). Retry-After: %s", retry_after_hdr)
            raise RateLimitedError("Server rate limit exceeded.", retry_after=retry_after_val)

        if response.status_code in (400, 413, 422):
            msg = f"Permanent API payload rejection (HTTP {response.status_code})"
            logger.error("%s: %s", msg, response.text[:200])
            raise PermanentPayloadError(msg)

        if response.status_code >= 500:
            logger.warning("Server error (HTTP %d) from %s", response.status_code, endpoint)
            raise TransientNetworkError(f"Server error (HTTP {response.status_code})")

        raise SyncClientError(
            f"Unexpected HTTP status {response.status_code}: {response.text[:200]}"
        )

    def send_heartbeat(
        self,
        queue_depth: int,
        state: str,
        agent_version: str = "3.0.0",
    ) -> dict[str, Any]:
        """Sends workstation status to POST /api/v1/devices/heartbeat."""
        endpoint = f"{self.api_base_url}/api/v1/devices/heartbeat"
        payload = {
            "agent_version": agent_version,
            "queue_depth": queue_depth,
            "state": state,
        }

        try:
            response = self._client.post(
                endpoint,
                json=payload,
                headers=self.auth_headers,
            )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TransientNetworkError(f"Heartbeat network error: {type(exc).__name__}") from exc

        if response.status_code == 200:
            return cast(dict[str, Any], response.json())

        if response.status_code in (401, 403):
            raise DeviceAuthError("Device credential unauthorized on heartbeat.")

        if response.status_code >= 500:
            raise TransientNetworkError(f"Server error on heartbeat (HTTP {response.status_code})")

        raise SyncClientError(f"Heartbeat failed with HTTP {response.status_code}")

    def close(self) -> None:
        """Closes the underlying HTTP client if owned."""
        if self._owns_client:
            self._client.close()
