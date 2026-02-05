from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers.auth import get_current_user
from src.api.schemas import (
    ErrorResponse,
    HabitCreate,
    HabitRead,
    HabitUpdate,
    HabitWithStats,
    StreakInfo,
)
from src.db.models import Habit, User
from src.db.session import get_db_session
from src.services.progress import (
    check_completed_this_week,
    check_completed_today,
    compute_streak_for_habit,
)

router = APIRouter(prefix="/habits", tags=["Habits"])


@router.post(
    "",
    response_model=HabitRead,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}},
    summary="Create a habit",
    description="Creates a new habit for the current user.",
    operation_id="habits_create",
)
async def create_habit(
    payload: HabitCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> HabitRead:
    """Create habit."""
    habit = Habit(
        user_id=current_user.id,
        name=payload.name,
        description=payload.description,
        schedule_type=payload.schedule_type,
        target_per_period=payload.target_per_period,
        is_active=payload.is_active,
    )
    session.add(habit)
    await session.commit()
    await session.refresh(habit)
    return HabitRead.model_validate(habit, from_attributes=True)


@router.get(
    "",
    response_model=list[HabitRead],
    summary="List habits",
    description="Lists the current user's habits.",
    operation_id="habits_list",
)
async def list_habits(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[HabitRead]:
    """List habits."""
    res = await session.execute(
        select(Habit).where(Habit.user_id == current_user.id).order_by(Habit.created_at.desc())
    )
    habits = res.scalars().all()
    return [HabitRead.model_validate(h, from_attributes=True) for h in habits]


@router.get(
    "/{habit_id}",
    response_model=HabitRead,
    responses={404: {"model": ErrorResponse}},
    summary="Get habit",
    description="Fetch a single habit owned by the current user.",
    operation_id="habits_get",
)
async def get_habit(
    habit_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> HabitRead:
    """Get habit."""
    res = await session.execute(select(Habit).where(Habit.id == habit_id, Habit.user_id == current_user.id))
    habit = res.scalar_one_or_none()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    return HabitRead.model_validate(habit, from_attributes=True)


@router.patch(
    "/{habit_id}",
    response_model=HabitRead,
    responses={404: {"model": ErrorResponse}},
    summary="Update habit",
    description="Updates fields on a habit owned by the current user.",
    operation_id="habits_update",
)
async def update_habit(
    habit_id: uuid.UUID,
    payload: HabitUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> HabitRead:
    """Update habit."""
    res = await session.execute(select(Habit).where(Habit.id == habit_id, Habit.user_id == current_user.id))
    habit = res.scalar_one_or_none()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(habit, k, v)

    await session.commit()
    await session.refresh(habit)
    return HabitRead.model_validate(habit, from_attributes=True)


@router.delete(
    "/{habit_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="Delete habit",
    description="Deletes a habit and its check-ins.",
    operation_id="habits_delete",
)
async def delete_habit(
    habit_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete habit."""
    res = await session.execute(select(Habit).where(Habit.id == habit_id, Habit.user_id == current_user.id))
    habit = res.scalar_one_or_none()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    await session.delete(habit)
    await session.commit()
    return None


@router.get(
    "/with-stats",
    response_model=list[HabitWithStats],
    summary="List habits with streaks and completion flags",
    description="Returns each habit plus its computed streak, and booleans for completed today/this week.",
    operation_id="habits_list_with_stats",
)
async def list_habits_with_stats(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[HabitWithStats]:
    """List habits with computed stats."""
    today = dt.date.today()
    res = await session.execute(
        select(Habit).where(Habit.user_id == current_user.id).order_by(Habit.created_at.desc())
    )
    habits = res.scalars().all()

    out: list[HabitWithStats] = []
    for h in habits:
        current, longest, last_date = await compute_streak_for_habit(
            session, user_id=current_user.id, habit_id=h.id
        )
        out.append(
            HabitWithStats(
                habit=HabitRead.model_validate(h, from_attributes=True),
                streak=StreakInfo(
                    current_streak_days=current,
                    longest_streak_days=longest,
                    last_checkin_date=last_date,
                ),
                completed_today=await check_completed_today(
                    session, user_id=current_user.id, habit_id=h.id, today=today
                ),
                completed_this_week=await check_completed_this_week(
                    session, user_id=current_user.id, habit_id=h.id, today=today
                ),
            )
        )
    return out
