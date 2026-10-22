"""EdgeErgo V3 — In-Memory Rate Limiting for Device Enrollment & Failed Authentication.

NOTE: This rate limiter uses in-memory tracking per API process instance.
In multi-instance production deployments (e.g., multi-worker uvicorn or multi-container Render),
rate limiting is enforced per-instance. For cluster-wide coordination across replicas,
a shared Redis or Memcached store can be wired in future phases.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock

from app.core.config import settings
from app.core.errors import RateLimitError


class InMemoryRateLimiter:
    """Sliding-window in-memory rate limiter per client key."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._events: dict[str, list[float]] = defaultdict(list)

    def check_rate_limit(self, key: str, max_requests: int, window_seconds: float = 60.0) -> None:
        """Checks if key exceeds max_requests within window_seconds.

        Raises RateLimitError if exceeded.
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            # Prune expired timestamps
            valid_timestamps = [t for t in self._events[key] if t > window_start]
            if len(valid_timestamps) >= max_requests:
                retry_after = int(valid_timestamps[0] + window_seconds - now) + 1
                raise RateLimitError(
                    message=f"Rate limit exceeded. Please retry after {retry_after} seconds.",
                    code="RATE_LIMITED",
                )

            valid_timestamps.append(now)
            self._events[key] = valid_timestamps

    def record_failure(self, key: str, max_failures: int, window_seconds: float = 60.0) -> None:
        """Records a failed attempt and enforces rate limits on subsequent failures."""
        self.check_rate_limit(
            f"fail:{key}", max_requests=max_failures, window_seconds=window_seconds
        )


# Global rate limiter instance
rate_limiter = InMemoryRateLimiter()


def enforce_enrollment_rate_limit(client_ip: str) -> None:
    """Enforces rate limit on device enrollment attempts."""
    rate_limiter.check_rate_limit(
        key=f"enroll:{client_ip}",
        max_requests=settings.ENROLLMENT_RATE_LIMIT_PER_MINUTE,
        window_seconds=60.0,
    )


def enforce_failed_auth_limit(client_ip: str) -> None:
    """Records and enforces rate limits on failed authentication attempts."""
    rate_limiter.record_failure(
        key=client_ip,
        max_failures=settings.FAILED_AUTH_RATE_LIMIT_PER_MINUTE,
        window_seconds=60.0,
    )
