"""EdgeErgo V3 — Supabase JWT & JWKS Verification Engine."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt
from jwt import PyJWK, PyJWKSet

from app.core.config import settings
from app.core.errors import AuthenticationError

logger = logging.getLogger("app.auth")


class JWKSClient:
    """Manages JWKS public key retrieval, caching, and rotation."""

    def __init__(self, jwks_url: str | None = None, cache_ttl_seconds: int = 3600) -> None:
        self.jwks_url = jwks_url or settings.SUPABASE_JWKS_URL
        self.cache_ttl = cache_ttl_seconds
        self._cached_jwks: PyJWKSet | None = None
        self._last_fetched: float = 0.0

    async def fetch_jwks(self) -> PyJWKSet:
        """Fetches public JWKS keys from remote endpoint."""
        # Validate that the JWKS URL has a valid scheme and host to prevent SSRF
        parsed = urlparse(self.jwks_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise AuthenticationError("Invalid JWKS URL configuration", code="CONFIG_ERROR")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.jwks_url)
                response.raise_for_status()
                data = response.json()
                self._cached_jwks = PyJWKSet.from_dict(data)
                self._last_fetched = time.time()
                return self._cached_jwks
        except Exception as exc:
            logger.error(f"Failed to fetch JWKS from {self.jwks_url}: {exc}")
            raise AuthenticationError(
                "Unable to verify token signature", code="JWKS_UNAVAILABLE"
            ) from exc

    async def get_signing_key(self, kid: str) -> PyJWK:
        """Retrieves signing key by kid, refreshing cache if unknown."""
        now = time.time()
        # If cache expired or not present, fetch
        if not self._cached_jwks or (now - self._last_fetched) > self.cache_ttl:
            await self.fetch_jwks()

        # Attempt to find key
        if self._cached_jwks:
            for key in self._cached_jwks.keys:
                if key.key_id == kid:
                    return key

        # If kid not found in existing cache, force one refresh (supports key rotation)
        logger.info(f"Key id '{kid}' not found in cache. Refreshing JWKS...")
        await self.fetch_jwks()
        if self._cached_jwks:
            for key in self._cached_jwks.keys:
                if key.key_id == kid:
                    return key

        raise AuthenticationError(f"Signing key with kid '{kid}' not found", code="INVALID_KEY_ID")

    def set_cached_jwks(self, jwks_dict: dict[str, Any]) -> None:
        """Explicitly sets cached keys (useful for unit testing)."""
        self._cached_jwks = PyJWKSet.from_dict(jwks_dict)
        self._last_fetched = time.time()


# Singleton JWKS client instance
jwks_client = JWKSClient()


async def verify_supabase_jwt(token: str) -> dict[str, Any]:
    """Verifies a Supabase Auth JWT token and returns the decoded payload.

    Enforces:
    - Algorithm allowlist (RS256, ES256, or optional legacy HS256)
    - Rejection of alg=none
    - Signature verification via JWKS
    - Expected issuer and audience
    - Expiration and not-before claims
    """
    if not token or not token.strip():
        raise AuthenticationError("Empty authentication token", code="MISSING_TOKEN")

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Malformed token header", code="INVALID_TOKEN") from exc

    alg = header.get("alg")
    if not alg or alg.lower() == "none":
        raise AuthenticationError(
            "Unsigned tokens (alg=none) are strictly forbidden", code="INSECURE_ALGORITHM"
        )

    allowed_algs = ["RS256", "ES256"]
    if settings.SUPABASE_JWT_SECRET:
        allowed_algs.append("HS256")

    if alg not in allowed_algs:
        raise AuthenticationError(
            f"Algorithm '{alg}' is not permitted", code="DISALLOWED_ALGORITHM"
        )

    # Decode options
    options: Any = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_nbf": True,
        "verify_iss": True,
        "verify_aud": True,
        "require": ["exp", "sub", "iss", "aud"],
    }

    payload: dict[str, Any]
    try:
        if alg == "HS256":
            if not settings.SUPABASE_JWT_SECRET:
                raise AuthenticationError(
                    "HS256 token received but secret not configured", code="CONFIG_ERROR"
                )
            payload = jwt.decode(
                token,
                key=settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                issuer=settings.SUPABASE_JWT_ISSUER,
                audience=settings.SUPABASE_JWT_AUDIENCE,
                options=options,
                leeway=10,
            )
        else:
            kid = header.get("kid")
            if not kid:
                raise AuthenticationError(
                    "Missing 'kid' in asymmetric token header", code="INVALID_HEADER"
                )
            signing_key = await jwks_client.get_signing_key(kid)
            payload = jwt.decode(
                token,
                key=signing_key.key,
                algorithms=[alg],
                issuer=settings.SUPABASE_JWT_ISSUER,
                audience=settings.SUPABASE_JWT_AUDIENCE,
                options=options,
                leeway=10,
            )
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token signature has expired", code="TOKEN_EXPIRED") from exc
    except jwt.ImmatureSignatureError as exc:
        raise AuthenticationError(
            "Token is not valid yet (nbf claim)", code="TOKEN_IMMATURE"
        ) from exc
    except jwt.InvalidIssuerError as exc:
        raise AuthenticationError("Token issuer claim is invalid", code="INVALID_ISSUER") from exc
    except jwt.InvalidAudienceError as exc:
        raise AuthenticationError(
            "Token audience claim is invalid", code="INVALID_AUDIENCE"
        ) from exc
    except jwt.InvalidSignatureError as exc:
        raise AuthenticationError(
            "Token signature verification failed", code="INVALID_SIGNATURE"
        ) from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError(
            f"Token verification failed: {exc}", code="INVALID_TOKEN"
        ) from exc
