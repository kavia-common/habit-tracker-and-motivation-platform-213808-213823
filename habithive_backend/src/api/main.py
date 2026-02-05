from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers.achievements import router as achievements_router
from src.api.routers.auth import router as auth_router
from src.api.routers.dashboard import router as dashboard_router
from src.api.routers.feed import router as feed_router
from src.api.routers.groups import router as groups_router
from src.api.routers.habits import router as habits_router
from src.api.routers.progress import router as progress_router
from src.core.settings import get_settings
from src.db.init_db import create_tables_and_seed
from src.db.session import close_engine, init_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler that initializes and disposes DB engine."""
    settings = get_settings()
    init_engine(settings)

    # Create tables and seed achievements.
    # Note: for larger projects use Alembic migrations; this is the step-03 persistence baseline.
    from src.db.session import _engine  # local import to avoid leaking in public interface

    assert _engine is not None
    await create_tables_and_seed(_engine)

    yield

    await close_engine()


openapi_tags = [
    {"name": "Auth", "description": "User registration/login and current-user profile."},
    {"name": "Habits", "description": "Habit CRUD and habit-level stats."},
    {"name": "Progress", "description": "Check-ins and progress logging."},
    {"name": "Dashboard", "description": "Aggregates for the dashboard."},
    {"name": "Groups", "description": "Accountability groups and memberships."},
    {"name": "Achievements", "description": "Badges/achievements available and earned."},
    {"name": "Activity Feed", "description": "Activity events feed (check-ins, achievements, groups)."},
]


app = FastAPI(
    title="HabitHive Backend API",
    description=(
        "HabitHive backend service providing authentication, habit tracking, progress logging, "
        "streak computation, dashboard aggregates, accountability groups, achievements/badges, "
        "and an activity feed."
    ),
    version="1.0.0",
    openapi_tags=openapi_tags,
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins if settings.cors_allow_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/",
    summary="Health check",
    description="Basic health check endpoint.",
    operation_id="health_check",
    tags=["Health"],
)
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}


@app.get(
    "/docs/help",
    summary="API usage help",
    description="High-level usage guide for the HabitHive API.",
    operation_id="docs_help",
    tags=["Health"],
)
def docs_help():
    """API usage notes for clients."""
    return {
        "auth": {
            "register": "POST /auth/register",
            "login": "POST /auth/login -> returns access_token",
            "usage": "Send Authorization: Bearer <token> on protected endpoints",
        },
        "core": {
            "habits": "CRUD under /habits",
            "checkins": "POST/GET /progress/habits/{habit_id}/checkins",
            "dashboard": "GET /dashboard/summary",
            "groups": "CRUD-ish under /groups (create/list/join/leave/members)",
            "achievements": "GET /achievements and /achievements/mine",
            "feed": "GET /feed",
        },
    }


# Routers
app.include_router(auth_router)
app.include_router(habits_router)
app.include_router(progress_router)
app.include_router(dashboard_router)
app.include_router(groups_router)
app.include_router(achievements_router)
app.include_router(feed_router)
