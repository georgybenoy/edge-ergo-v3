"""Pytest configuration and database fixtures for backend tests."""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def _is_db_accessible(dsn: str) -> bool:
    try:
        conn = psycopg.connect(dsn, connect_timeout=1)
        conn.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def postgres_test_dsn() -> Generator[str, None, None]:
    """Provides a PostgreSQL connection DSN for testing.

    Uses TEST_DATABASE_URL from environment if accessible.
    Otherwise, starts an ephemeral local PostgreSQL instance on Windows/Linux.
    """
    env_dsn = os.getenv(
        "TEST_DATABASE_URL", "postgresql://postgres:password@localhost:5432/edgeergo_test"
    )

    if _is_db_accessible(env_dsn):
        yield env_dsn
        return

    # Check for local PostgreSQL binary on Windows
    pg_bin_dir = Path("C:/Program Files/PostgreSQL/18/bin")
    initdb_exe = pg_bin_dir / "initdb.exe"
    pg_ctl_exe = pg_bin_dir / "pg_ctl.exe"
    createdb_exe = pg_bin_dir / "createdb.exe"

    if not initdb_exe.exists():
        pytest.skip("PostgreSQL test database not accessible and initdb not found.")

    repo_root = Path(__file__).resolve().parent.parent.parent
    cluster_dir = repo_root / "scratch" / "test_cluster"
    data_dir = cluster_dir / "data"
    log_file = cluster_dir / "pg.log"
    port = 54329
    test_db_dsn = f"host=127.0.0.1 port={port} user=postgres dbname=edgeergo_test"

    cluster_dir.mkdir(parents=True, exist_ok=True)
    if not (data_dir / "PG_VERSION").exists():
        subprocess.run(
            [
                str(initdb_exe),
                "-D",
                str(data_dir),
                "-U",
                "postgres",
                "-A",
                "trust",
                "--encoding=UTF8",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    # Start ephemeral server (DEVNULL avoids hanging on daemon pipes)
    subprocess.run(
        [str(pg_ctl_exe), "-D", str(data_dir), "-l", str(log_file), "-o", f"-p {port}", "start"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)

    # Ensure edgeergo_test database exists
    subprocess.run(
        [str(createdb_exe), "-h", "127.0.0.1", "-p", str(port), "-U", "postgres", "edgeergo_test"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        yield test_db_dsn
    finally:
        subprocess.run(
            [str(pg_ctl_exe), "-D", str(data_dir), "-m", "immediate", "stop"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


@pytest.fixture
def clean_db(
    postgres_test_dsn: str,
) -> Generator[psycopg.Connection[tuple[object, ...]], None, None]:
    """Provides a clean test database with auth stub applied."""
    conn = psycopg.connect(postgres_test_dsn, autocommit=False, connect_timeout=5)

    try:
        conn.rollback()
    except Exception:
        pass

    # Clean public and auth schemas
    with conn.cursor() as cur:
        cur.execute(
            """
            DROP SCHEMA IF EXISTS public CASCADE;
            DROP SCHEMA IF EXISTS auth CASCADE;
            CREATE SCHEMA public;
            GRANT ALL ON SCHEMA public TO postgres;
            GRANT ALL ON SCHEMA public TO public;
            """
        )
    conn.commit()

    # Apply auth stub
    repo_root = Path(__file__).resolve().parent.parent.parent
    auth_stub_path = repo_root / "supabase" / "tests" / "setup_test_db.sql"
    auth_stub_sql = auth_stub_path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(auth_stub_sql)
    conn.commit()

    yield conn

    try:
        conn.rollback()
    except Exception:
        pass
    conn.close()


def dsn_to_url(dsn: str) -> str:
    """Converts a psycopg key-value DSN or standard URI into a postgresql+asyncpg URL."""
    if dsn.startswith("postgresql://") or dsn.startswith("postgres://"):
        return dsn.replace("postgres://", "postgresql+asyncpg://").replace(
            "postgresql://", "postgresql+asyncpg://"
        )
    # Parse key=value pairs
    parts = dict(part.split("=", 1) for part in dsn.split())
    host = parts.get("host", "127.0.0.1")
    port = parts.get("port", "5432")
    user = parts.get("user", "postgres")
    dbname = parts.get("dbname", "edgeergo_test")
    return f"postgresql+asyncpg://{user}@{host}:{port}/{dbname}"


class TestJWTSigner:
    """Mints asymmetric RS256/HS256 test tokens and injects keys into JWKSClient."""

    def __init__(self) -> None:
        import json

        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa

        from app.core.auth import jwks_client
        from app.core.config import settings

        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.public_key = self.private_key.public_key()
        self.kid = "test_key_kid_1"
        self.algorithm = "RS256"

        # Generate JWK
        jwk_json = jwt.algorithms.RSAAlgorithm.to_jwk(self.public_key)
        jwk_dict = json.loads(jwk_json)
        jwk_dict["kid"] = self.kid
        jwk_dict["alg"] = self.algorithm

        # Cache in jwks_client
        jwks_client.set_cached_jwks({"keys": [jwk_dict]})
        self.jwks_client = jwks_client
        self.settings = settings

    def mint_token(
        self,
        user_id: str,
        email: str = "testuser@example.com",
        role: str = "authenticated",
        issuer: str | None = None,
        audience: str | None = None,
        kid: str | None = None,
        algorithm: str = "RS256",
        expires_delta_seconds: int = 3600,
        nbf_delta_seconds: int = -10,
        custom_claims: dict[str, object] | None = None,
        signing_key: Any = None,
    ) -> str:
        import time

        import jwt

        now = int(time.time())
        payload: dict[str, object] = {
            "sub": user_id,
            "email": email,
            "role": role,
            "iss": issuer or self.settings.SUPABASE_JWT_ISSUER,
            "aud": audience or self.settings.SUPABASE_JWT_AUDIENCE,
            "iat": now,
            "exp": now + expires_delta_seconds,
            "nbf": now + nbf_delta_seconds,
        }
        if custom_claims:
            payload.update(custom_claims)

        key: Any = signing_key or self.private_key
        headers: dict[str, object] = {}
        if algorithm != "none":
            headers["kid"] = kid or self.kid

        if algorithm == "none":
            return jwt.encode(payload, key="", algorithm="none")

        return jwt.encode(payload, key, algorithm=algorithm, headers=headers)


@pytest.fixture
def jwt_signer() -> TestJWTSigner:
    """Provides a JWT signer configured with local RSA keys and mocked JWKS."""
    return TestJWTSigner()


@pytest.fixture
async def async_test_session(
    clean_db: psycopg.Connection[tuple[object, ...]],
    postgres_test_dsn: str,
) -> AsyncGenerator[AsyncSession, None]:
    """Runs migrations and yields an active AsyncSession connected to test database."""
    from app.db.migrations import run_migrations

    # Ensure schema migrations applied
    run_migrations(clean_db)

    url = dsn_to_url(postgres_test_dsn)
    engine = create_async_engine(
        url,
        echo=False,
        future=True,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def async_client(
    async_test_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provides an httpx.AsyncClient with database dependency overridden to test DB."""
    from httpx import ASGITransport

    from app.db.session import get_db
    from app.main import app

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield async_test_session

    app.dependency_overrides[get_db] = override_get_db

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client

    app.dependency_overrides.clear()
