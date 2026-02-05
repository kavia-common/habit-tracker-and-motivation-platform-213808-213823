from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers.auth import get_current_user
from src.api.schemas import DashboardSummary
from src.db.models import Habit, HabitCheckIn, UserAchievement, User
from src.db.session import get_db_session
from src.services.progress import compute_streak_for_habit

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Dashboard summary aggregates",
    description="Returns counts for active habits, last 7 days check-ins, best current streak, and achievements count.",
    operation_id="dashboard_summary",
)
async def summary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardSummary:
    """Dashboard aggregate endpoint."""
    active_habits_res = await session.execute(
        select(func.count(Habit.id)).where(Habit.user_id == current_user.id, Habit.is_active.is_(True))
    )
    active_habits = int(active_habits_res.scalar_one() or 0)

    today = dt.date.today()
    week_ago = today - dt.timedelta(days=6)
    last_7_res = await session.execute(
        select(func.count(HabitCheckIn.id)).where(
            HabitCheckIn.user_id == current_user.id,
            HabitCheckIn.checkin_date >= week_ago,
            HabitCheckIn.checkin_date <= today,
        )
    )
    checkins_last_7 = int(last_7_res.scalar_one() or 0)

    ach_res = await session.execute(
        select(func.count(UserAchievement.id)).where(UserAchievement.user_id == current_user.id)
    )
    achievements_count = int(ach_res.scalar_one() or 0)

    # Best current streak across habits = max(current streak)
    habits_res = await session.execute(select(Habit.id).where(Habit.user_id == current_user.id))
    habit_ids = [r[0] for r in habits_res.all()]
    best_current = 0
    for hid in habit_ids:
        current, _, _ = await compute_streak_for_habit(session, user_id=current_user.id, habit_id=hid)
        best_current = max(best_current, current)

    return DashboardSummary(
        active_habits=active_habits,
        checkins_last_7_days=checkins_last_7,
        current_best_streak=best_current,
        achievements_count=achievements_count,
    )
