from __future__ import annotations

from collections.abc import AsyncGenerator
import os
import re

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.settings import Settings

_engine: AsyncEngine | None = None
_session_maker: async_sessionmaker[AsyncSession] | None = None


def _coerce_to_async_sqlalchemy_url(raw_url: str) -> str:
    """Convert a postgres URL to a SQLAlchemy asyncpg URL.

    Accepts:
      - postgresql://...
      - postgres://...
      - postgresql+asyncpg://... (already async)

    Returns:
        str: postgresql+asyncpg://...
    """
    raw_url = raw_url.strip()
    if raw_url.startswith("postgresql+asyncpg://"):
        return raw_url
    if raw_url.startswith("postgres://"):
        raw_url = "postgresql://" + raw_url[len("postgres://") :]
    if raw_url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + raw_url[len("postgresql://") :]
    raise ValueError("Unsupported Postgres URL scheme")


def _read_db_connection_txt() -> str | None:
    """Read DB connection info from db_connection.txt (platform convention).

    The Postgres skill guidance says this file typically contains:
      psql postgresql://user:pass@host:port/db

    We parse and extract the first postgresql/postgres URL found.
    """
    candidates = [
        # Common locations depending on container/workspace layouts
        os.path.join(os.getcwd(), "db_connection.txt"),
        os.path.join(os.getcwd(), "..", "db_connection.txt"),
    ]
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
        except OSError:
            continue

        # Extract a postgres URL from either a plain URL or a `psql <url>` line.
        m = re.search(r"(postgresql:\/\/\S+|postgres:\/\/\S+)", content)
        if m:
            return m.group(1).strip().rstrip(";")
    return None


def _build_database_url(settings: Settings) -> str:
    """Build a Postgres DSN for SQLAlchemy async engine.

    Priority order:
      1) db_connection.txt (if present)
      2) POSTGRES_URL if it is a full postgres URL
      3) POSTGRES_* discrete vars (host in POSTGRES_URL; other parts from env or defaults)

    Sane defaults are provided for user/db/port to reduce friction in preview environments.

    Returns:
        str: A SQLAlchemy async URL (postgresql+asyncpg://...).
    """
    # 1) Prefer db_connection.txt if present (platform convention for DB containers).
    raw_from_file = _read_db_connection_txt()
    if raw_from_file:
        try:
            return _coerce_to_async_sqlalchemy_url(raw_from_file)
        except ValueError:
            # Fall through to env-based config if file contents are unexpected.
            pass

    # 2) If POSTGRES_URL is a full URL, adapt scheme for SQLAlchemy async.
    if settings.postgres_url:
        raw = settings.postgres_url.strip()
        if raw.startswith("postgresql://") or raw.startswith("postgres://") or raw.startswith(
            "postgresql+asyncpg://"
        ):
            return _coerce_to_async_sqlalchemy_url(raw)

    # 3) Otherwise treat POSTGRES_URL as host (optionally host:port) and use discrete vars.
    host = (settings.postgres_url or "").strip()
    if not host:
        raise RuntimeError(
            "Database configuration missing. Provide db_connection.txt or POSTGRES_URL / POSTGRES_* env vars."
        )

    user = (settings.postgres_user or "appuser").strip()
    password = (settings.postgres_password or "apppassword").strip()
    db = (settings.postgres_db or "appdb").strip()

    # If host already includes port, prefer it; else use POSTGRES_PORT (or default 5001).
    port = (settings.postgres_port or "5001").strip()
    host_port = host if ":" in host else f"{host}:{port}"

    return f"postgresql+asyncpg://{user}:{password}@{host_port}/{db}"


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
