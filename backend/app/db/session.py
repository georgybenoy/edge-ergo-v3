"""EdgeErgo V3 — Database Engine, Async Session, & Pooler Compatibility Configuration."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def normalize_async_database_url(url: str) -> str:
    """Converts postgresql:// or postgres:// to postgresql+asyncpg:// for async SQLAlchemy."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def get_engine(database_url: str | None = None) -> AsyncEngine:
    """Creates a configured AsyncEngine with Supabase transaction pooler compatibility."""
    url = normalize_async_database_url(database_url or settings.DATABASE_URL)

    # Supabase Transaction Pooler (port 6543) Compatibility:
    # Transaction poolers reassign physical connections between transactions.
    # Prepared statement caching must be disabled to avoid caching conflicts.
    connect_args: dict[str, object] = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }

    return create_async_engine(
        url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=300,
        connect_args=connect_args,
    )


# Default application engine and session factory
engine = get_engine()
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a transactional AsyncSession."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def transactional_session(session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """Unit-of-work context manager ensuring atomic transaction commit or rollback."""
    if session.in_transaction():
        yield session
    else:
        async with session.begin():
            yield session
