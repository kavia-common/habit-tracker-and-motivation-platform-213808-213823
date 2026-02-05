from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from src.db.models import Achievement, Base


DEFAULT_ACHIEVEMENTS = [
    {
        "code": "FIRST_CHECKIN",
        "name": "First Steps",
        "description": "Log your first habit check-in.",
        "icon": "spark",
    },
    {
        "code": "STREAK_7",
        "name": "Lucky 7",
        "description": "Maintain a 7-day streak on any habit.",
        "icon": "flame",
    },
    {
        "code": "STREAK_30",
        "name": "30-Day Champion",
        "description": "Maintain a 30-day streak on any habit.",
        "icon": "trophy",
    },
    {
        "code": "CHECKINS_50",
        "name": "Consistency",
        "description": "Log 50 total check-ins.",
        "icon": "badge",
    },
]


# PUBLIC_INTERFACE
async def create_tables_and_seed(engine: AsyncEngine) -> None:
    """Create DB tables (if missing) and seed base achievements.

    This intentionally avoids Alembic for this project step. It uses SQLAlchemy
    metadata create_all on startup.

    Args:
        engine: Async SQLAlchemy engine.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed achievements idempotently
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        for a in DEFAULT_ACHIEVEMENTS:
            existing = await session.execute(select(Achievement).where(Achievement.code == a["code"]))
            if existing.scalar_one_or_none() is None:
                session.add(Achievement(**a))
        await session.commit()
