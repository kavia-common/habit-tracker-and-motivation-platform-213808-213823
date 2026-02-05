from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers.auth import get_current_user
from src.api.schemas import ActivityEventRead
from src.db.models import ActivityEvent, GroupMember, User
from src.db.session import get_db_session

router = APIRouter(prefix="/feed", tags=["Activity Feed"])


@router.get(
    "",
    response_model=list[ActivityEventRead],
    summary="Get activity feed",
    description=(
        "Returns recent activity events for the user.\n\n"
        "v1 behavior: includes the user's own events and events from users who share a group with them."
    ),
    operation_id="feed_list",
)
async def list_feed(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ActivityEventRead]:
    """Activity feed."""
    # Get group ids the user belongs to
    g_ids_res = await session.execute(
        select(GroupMember.group_id).where(GroupMember.user_id == current_user.id)
    )
    group_ids = [r[0] for r in g_ids_res.all()]

    if group_ids:
        # Find peer user ids sharing those groups
        peers_res = await session.execute(
            select(GroupMember.user_id).where(GroupMember.group_id.in_(group_ids))
        )
        peer_user_ids = list({r[0] for r in peers_res.all()})
    else:
        peer_user_ids = [current_user.id]

    res = await session.execute(
        select(ActivityEvent)
        .where(ActivityEvent.user_id.in_(peer_user_ids))
        .order_by(ActivityEvent.created_at.desc())
        .limit(limit)
    )
    events = res.scalars().all()
    return [ActivityEventRead.model_validate(e, from_attributes=True) for e in events]
