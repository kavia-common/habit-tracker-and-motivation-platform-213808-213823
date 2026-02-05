from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers.auth import get_current_user
from src.api.schemas import AchievementRead, UserAchievementRead
from src.db.models import Achievement, User, UserAchievement
from src.db.session import get_db_session

router = APIRouter(prefix="/achievements", tags=["Achievements"])


@router.get(
    "",
    response_model=list[AchievementRead],
    summary="List available achievements",
    description="Lists all achievements defined by the system.",
    operation_id="achievements_list",
)
async def list_achievements(session: AsyncSession = Depends(get_db_session)) -> list[AchievementRead]:
    """List system achievements."""
    res = await session.execute(select(Achievement).order_by(Achievement.created_at.asc()))
    items = res.scalars().all()
    return [AchievementRead.model_validate(a, from_attributes=True) for a in items]


@router.get(
    "/mine",
    response_model=list[UserAchievementRead],
    summary="List my achievements",
    description="Lists achievements awarded to the current user.",
    operation_id="achievements_list_mine",
)
async def list_my_achievements(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[UserAchievementRead]:
    """List achievements for current user."""
    res = await session.execute(
        select(UserAchievement)
        .join(Achievement, Achievement.id == UserAchievement.achievement_id)
        .where(UserAchievement.user_id == current_user.id)
        .order_by(UserAchievement.awarded_at.desc())
    )
    uas = res.scalars().all()

    # Eager serialize embedded achievement
    out: list[UserAchievementRead] = []
    for ua in uas:
        out.append(
            UserAchievementRead(
                id=ua.id,
                user_id=ua.user_id,
                achievement_id=ua.achievement_id,
                awarded_at=ua.awarded_at,
                achievement=AchievementRead.model_validate(ua.achievement, from_attributes=True),
            )
        )
    return out
