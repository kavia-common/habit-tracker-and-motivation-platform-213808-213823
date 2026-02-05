from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.settings import Settings

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def _build_database_url(settings: Settings) -> str:
    """Build a Postgres DSN from the platform env vars.

    This respects the platform's database container variables:
    POSTGRES_URL, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_PORT

    Returns:
        str: A SQLAlchemy async URL (postgresql+asyncpg://...).
    """
    # POSTGRES_URL can be either:
    # - a full URL (postgresql://user:pass@host:port/db)
    # - a host/address (host or host:port)
    # We'll accept both.
    if settings.postgres_url:
        raw = settings.postgres_url.strip()

        # If it's a full URL, adapt scheme for SQLAlchemy async.
        if raw.startswith("postgresql://") or raw.startswith("postgres://"):
            # normalize scheme then swap to async
            if raw.startswith("postgres://"):
                raw = "postgresql://" + raw[len("postgres://") :]
            return "postgresql+asyncpg://" + raw[len("postgresql://") :]

        # Otherwise treat it as host (optionally host:port)
        host_port = raw
        user = settings.postgres_user or ""
        password = settings.postgres_password or ""
        db = settings.postgres_db or ""
        port = settings.postgres_port or ""

        # If host_port already includes port, prefer it; else use POSTGRES_PORT.
        if ":" not in host_port and port:
            host_port = f"{host_port}:{port}"

        return f"postgresql+asyncpg://{user}:{password}@{host_port}/{db}"

    # Fallback: construct from discrete pieces (requires host in POSTGRES_URL).
    raise RuntimeError(
        "Database configuration missing. Provide POSTGRES_URL (host or full URL) "
        "and related POSTGRES_* env vars in the backend container."
    )


# PUBLIC_INTERFACE
def init_engine(settings: Settings) -> None:
    """Initialize global async DB engine and session maker.

    This must be called once at app startup.

    Args:
        settings: Application settings.

    Raises:
        RuntimeError: If engine is already initialized.
    """
    global _engine, _session_maker
    if _engine is not None or _session_maker is not None:
        raise RuntimeError("DB engine already initialized")

    db_url = _build_database_url(settings)
    _engine = create_async_engine(
        db_url,
        pool_pre_ping=True,
        future=True,
    )
    _session_maker = async_sessionmaker(_engine, expire_on_commit=False)


# PUBLIC_INTERFACE
async def close_engine() -> None:
    """Dispose the DB engine at shutdown."""
    global _engine, _session_maker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_maker = None


# PUBLIC_INTERFACE
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession."""
    if _session_maker is None:
        raise RuntimeError("DB engine not initialized. Call init_engine() on startup.")
    async with _session_maker() as session:
        yield session
