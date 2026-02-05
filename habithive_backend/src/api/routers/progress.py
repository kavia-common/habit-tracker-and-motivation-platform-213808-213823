from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers.auth import get_current_user
from src.api.schemas import CheckInCreate, CheckInRead, ErrorResponse
from src.db.models import Habit, HabitCheckIn, User
from src.db.session import get_db_session
from src.services.progress import evaluate_and_award_achievements

router = APIRouter(prefix="/progress", tags=["Progress"])


@router.post(
    "/habits/{habit_id}/checkins",
    response_model=CheckInRead,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Create a habit check-in",
    description="Logs a check-in for a habit (unique per date). Also triggers achievement awarding.",
    operation_id="progress_create_checkin",
)
async def create_checkin(
    habit_id: uuid.UUID,
    payload: CheckInCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CheckInRead:
    """Create check-in for a habit owned by the current user."""
    hres = await session.execute(select(Habit).where(Habit.id == habit_id, Habit.user_id == current_user.id))
    habit = hres.scalar_one_or_none()
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    checkin = HabitCheckIn(
        habit_id=habit_id,
        user_id=current_user.id,
        checkin_date=payload.checkin_date,
        count=payload.count,
        note=payload.note,
    )
    session.add(checkin)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Check-in for this date already exists")

    # Trigger achievements + activity events
    await evaluate_and_award_achievements(session, user_id=current_user.id, habit_id=habit_id)

    await session.commit()
    await session.refresh(checkin)
    return CheckInRead.model_validate(checkin, from_attributes=True)


@router.get(
    "/habits/{habit_id}/checkins",
    response_model=list[CheckInRead],
    responses={404: {"model": ErrorResponse}},
    summary="List habit check-ins",
    description="Lists check-ins for a habit owned by the current user (most recent first).",
    operation_id="progress_list_checkins",
)
async def list_checkins(
    habit_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[CheckInRead]:
    """List check-ins for a habit."""
    hres = await session.execute(select(Habit.id).where(Habit.id == habit_id, Habit.user_id == current_user.id))
    if hres.first() is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    res = await session.execute(
        select(HabitCheckIn)
        .where(HabitCheckIn.habit_id == habit_id, HabitCheckIn.user_id == current_user.id)
        .order_by(HabitCheckIn.checkin_date.desc(), HabitCheckIn.created_at.desc())
    )
    checkins = res.scalars().all()
    return [CheckInRead.model_validate(c, from_attributes=True) for c in checkins]
