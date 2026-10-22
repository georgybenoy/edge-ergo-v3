"""EdgeErgo V3 — Hosted API Configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings validated from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Core Application
    APP_NAME: str = "EdgeErgo Hosted API"
    APP_VERSION: str = "3.0.0"
    APP_ENV: str = Field(
        default="development",
        description="Runtime environment: development, test, production",
    )
    API_V1_PREFIX: str = Field(default="/api/v1", description="Prefix for V1 API routes")
    FRONTEND_ORIGIN: str = Field(default="http://localhost:5173", description="Allowed CORS origin")

    # Supabase Auth Configuration
    SUPABASE_URL: str = Field(
        default="https://placeholder.supabase.co",
        description="Supabase project URL",
    )
    SUPABASE_JWT_ISSUER: str = Field(
        default="https://placeholder.supabase.co/auth/v1",
        description="Expected JWT issuer",
    )
    SUPABASE_JWKS_URL: str = Field(
        default="https://placeholder.supabase.co/auth/v1/.well-known/jwks.json",
        description="Public JWKS endpoint for asymmetric JWT verification",
    )
    SUPABASE_JWT_AUDIENCE: str = Field(
        default="authenticated",
        description="Expected JWT audience claim",
    )

    # Database Connections
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://edgeergo_api_user:password@localhost:5432/postgres",
        description="PostgreSQL connection string using dedicated least-privilege role",
    )
    TEST_DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/edgeergo_test",
        description="Isolated database connection for automated test suites",
    )

    # Operational Parameters
    LOG_LEVEL: str = Field(default="INFO", description="Log verbosity")
    ENROLLMENT_TOKEN_TTL_MINUTES: int = Field(
        default=15,
        description="Device enrollment token expiry time in minutes",
    )
    MAX_BATCH_SIZE: int = Field(
        default=100,
        description="Max assessment events per upload batch",
    )
    MAX_EXPORT_ROWS: int = Field(
        default=10000,
        description="Max rows returned in a single export request",
    )
    MAX_REQUEST_BODY_SIZE_BYTES: int = Field(
        default=2 * 1024 * 1024,
        description="Maximum request payload size in bytes (2MB default)",
    )
    DEVICE_ONLINE_WINDOW_SECONDS: int = Field(
        default=180,
        description="Window in seconds within which a device is considered online (3x interval)",
    )
    ENROLLMENT_RATE_LIMIT_PER_MINUTE: int = Field(
        default=10,
        description="Max enrollment attempts per minute per IP",
    )
    FAILED_AUTH_RATE_LIMIT_PER_MINUTE: int = Field(
        default=20,
        description="Max failed authentication attempts per minute per IP",
    )
    ENABLE_API_DOCS: bool = Field(
        default=True,
        description="Enable /docs and /redoc endpoints (disabled by default in production)",
    )

    ALLOW_LOCAL_PROD_TEST: bool = Field(
        default=False,
        description="Allow local database/origin in prod mode for local testing",
    )

    # Optional Server-Only Variables (NOT required for normal least-privilege operations)
    SUPABASE_SERVICE_ROLE_KEY: str | None = Field(
        default=None,
        description="Optional server-only key. Never exposed to browser or edge agent.",
    )
    SUPABASE_JWT_SECRET: str | None = Field(
        default=None,
        description="Optional legacy HS256 secret for local development/testing only.",
    )

    @classmethod
    def validate_production(cls, values: Settings) -> None:
        """Enforces strict fail-closed constraints when APP_ENV is production."""
        if values.APP_ENV == "production" and not values.ALLOW_LOCAL_PROD_TEST:
            errors: list[str] = []
            if "placeholder" in values.SUPABASE_URL.lower():
                errors.append("SUPABASE_URL must be set to a valid URL in production.")
            if "placeholder" in values.SUPABASE_JWT_ISSUER.lower():
                errors.append("SUPABASE_JWT_ISSUER must be set to a valid issuer in production.")
            if "placeholder" in values.SUPABASE_JWKS_URL.lower():
                errors.append(
                    "SUPABASE_JWKS_URL must be set to a valid JWKS endpoint in production."
                )
            if "localhost" in values.DATABASE_URL.lower() or "password@" in values.DATABASE_URL:
                errors.append("DATABASE_URL must be set to a production database connection.")
            if (
                not values.FRONTEND_ORIGIN
                or values.FRONTEND_ORIGIN == "*"
                or "localhost" in values.FRONTEND_ORIGIN.lower()
            ):
                errors.append(
                    "FRONTEND_ORIGIN must be explicitly set to a production origin (no wildcards)."
                )
            if values.ENABLE_API_DOCS:
                errors.append("ENABLE_API_DOCS must be set to False in production.")

            if errors:
                raise ValueError("Production configuration failed closed:\n" + "\n".join(errors))

    def model_post_init(self, __context: object) -> None:
        self.validate_production(self)


# Singleton settings instance
settings = Settings()
