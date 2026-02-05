from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Achievement, ActivityEvent, Habit, HabitCheckIn, UserAchievement


def _week_start(d: dt.date) -> dt.date:
    """Monday-based week start."""
    return d - dt.timedelta(days=d.weekday())


# PUBLIC_INTERFACE
async def compute_streak_for_habit(
    session: AsyncSession, *, user_id: uuid.UUID, habit_id: uuid.UUID
) -> tuple[int, int, dt.date | None]:
    """Compute current and longest streak (days) for a habit.

    Definition (v1):
      - A "streak day" is a calendar day with >=1 check-in count for the habit.
      - Streak increments for consecutive days ending today or yesterday (we consider
        "current streak" as consecutive days ending at the most recent check-in date).

    Returns:
        (current_streak_days, longest_streak_days, last_checkin_date)
    """
    rows = await session.execute(
        select(HabitCheckIn.checkin_date)
        .where(HabitCheckIn.user_id == user_id, HabitCheckIn.habit_id == habit_id)
        .order_by(HabitCheckIn.checkin_date.asc())
    )
    dates = [r[0] for r in rows.all()]
    if not dates:
        return 0, 0, None

    longest = 1
    current_run = 1
    best_run = 1
    for i in range(1, len(dates)):
        delta = (dates[i] - dates[i - 1]).days
        if delta == 1:
            current_run += 1
        elif delta == 0:
            # same date duplicated should not happen due to unique constraint, but ignore gracefully
            continue
        else:
            best_run = max(best_run, current_run)
            current_run = 1
    best_run = max(best_run, current_run)
    longest = best_run

    last_date = dates[-1]
    # current streak: consecutive days ending on last_date (already in current_run if last segment)
    # need to recompute last segment length
    seg_len = 1
    for j in range(len(dates) - 1, 0, -1):
        if (dates[j] - dates[j - 1]).days == 1:
            seg_len += 1
        else:
            break

    return seg_len, longest, last_date


# PUBLIC_INTERFACE
async def check_completed_today(
    session: AsyncSession, *, user_id: uuid.UUID, habit_id: uuid.UUID, today: dt.date
) -> bool:
    """Return whether the user has a check-in for habit on today."""
    res = await session.execute(
        select(HabitCheckIn.id).where(
            HabitCheckIn.user_id == user_id,
            HabitCheckIn.habit_id == habit_id,
            HabitCheckIn.checkin_date == today,
        )
    )
    return res.first() is not None


# PUBLIC_INTERFACE
async def check_completed_this_week(
    session: AsyncSession, *, user_id: uuid.UUID, habit_id: uuid.UUID, today: dt.date
) -> bool:
    """Return whether the user has any check-in for habit in the current week."""
    start = _week_start(today)
    res = await session.execute(
        select(HabitCheckIn.id).where(
            HabitCheckIn.user_id == user_id,
            HabitCheckIn.habit_id == habit_id,
            HabitCheckIn.checkin_date >= start,
            HabitCheckIn.checkin_date <= today,
        )
    )
    return res.first() is not None


async def _award_achievement_if_missing(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    code: str,
    activity_message: str,
) -> bool:
    """Award an achievement by code if the user doesn't already have it."""
    a_res = await session.execute(select(Achievement).where(Achievement.code == code))
    achievement = a_res.scalar_one_or_none()
    if achievement is None:
        return False

    existing = await session.execute(
        select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False

    session.add(UserAchievement(user_id=user_id, achievement_id=achievement.id))
    session.add(ActivityEvent(user_id=user_id, event_type="achievement", message=activity_message))
    return True


# PUBLIC_INTERFACE
async def evaluate_and_award_achievements(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    habit_id: uuid.UUID,
) -> list[str]:
    """Evaluate and award achievements triggered after a check-in.

    Returns:
        list[str]: List of achievement codes newly awarded.
    """
    newly: list[str] = []

    # FIRST_CHECKIN
    total_checkins_res = await session.execute(
        select(func.count(HabitCheckIn.id)).where(HabitCheckIn.user_id == user_id)
    )
    total_checkins = int(total_checkins_res.scalar_one() or 0)

    if total_checkins == 1:
        did = await _award_achievement_if_missing(
            session,
            user_id=user_id,
            code="FIRST_CHECKIN",
            activity_message="Earned 'First Steps' badge!",
        )
        if did:
            newly.append("FIRST_CHECKIN")

    # CHECKINS_50
    if total_checkins >= 50:
        did = await _award_achievement_if_missing(
            session,
            user_id=user_id,
            code="CHECKINS_50",
            activity_message="Earned 'Consistency' badge for 50 check-ins!",
        )
        if did:
            newly.append("CHECKINS_50")

    # streak-based
    current_streak, longest_streak, _ = await compute_streak_for_habit(
        session, user_id=user_id, habit_id=habit_id
    )

    if longest_streak >= 7:
        did = await _award_achievement_if_missing(
            session,
            user_id=user_id,
            code="STREAK_7",
            activity_message="Earned 'Lucky 7' badge for a 7-day streak!",
        )
        if did:
            newly.append("STREAK_7")

    if longest_streak >= 30:
        did = await _award_achievement_if_missing(
            session,
            user_id=user_id,
            code="STREAK_30",
            activity_message="Earned '30-Day Champion' badge for a 30-day streak!",
        )
        if did:
            newly.append("STREAK_30")

    # record check-in activity event (not an achievement)
    habit_res = await session.execute(
        select(Habit).where(Habit.id == habit_id, Habit.user_id == user_id)
    )
    habit = habit_res.scalar_one_or_none()
    if habit is not None:
        session.add(
            ActivityEvent(
                user_id=user_id,
                event_type="checkin",
                message=f"Checked in: {habit.name}",
            )
        )

    return newly
