from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers.auth import get_current_user
from src.api.schemas import ErrorResponse, GroupCreate, GroupMemberRead, GroupRead
from src.db.models import ActivityEvent, Group, GroupMember, User
from src.db.session import get_db_session

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.post(
    "",
    response_model=GroupRead,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}},
    summary="Create group",
    description="Creates a group and adds the creator as admin.",
    operation_id="groups_create",
)
async def create_group(
    payload: GroupCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> GroupRead:
    """Create group."""
    group = Group(name=payload.name, description=payload.description, created_by_user_id=current_user.id)
    session.add(group)
    await session.flush()
    session.add(GroupMember(group_id=group.id, user_id=current_user.id, role="admin"))
    session.add(
        ActivityEvent(user_id=current_user.id, event_type="group", message=f"Created group: {group.name}")
    )
    await session.commit()
    await session.refresh(group)
    return GroupRead.model_validate(group, from_attributes=True)


@router.get(
    "",
    response_model=list[GroupRead],
    summary="List groups",
    description="Lists groups the current user belongs to.",
    operation_id="groups_list",
)
async def list_groups(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[GroupRead]:
    """List groups by membership."""
    res = await session.execute(
        select(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == current_user.id)
        .order_by(Group.created_at.desc())
    )
    groups = res.scalars().all()
    return [GroupRead.model_validate(g, from_attributes=True) for g in groups]


@router.post(
    "/{group_id}/join",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Join group",
    description="Joins an existing group as member.",
    operation_id="groups_join",
)
async def join_group(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Join a group."""
    gres = await session.execute(select(Group).where(Group.id == group_id))
    group = gres.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    membership = GroupMember(group_id=group_id, user_id=current_user.id, role="member")
    session.add(membership)
    try:
        await session.flush()
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Already a member")

    session.add(
        ActivityEvent(user_id=current_user.id, event_type="group", message=f"Joined group: {group.name}")
    )
    await session.commit()
    return None


@router.post(
    "/{group_id}/leave",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
    summary="Leave group",
    description="Leaves a group if a member.",
    operation_id="groups_leave",
)
async def leave_group(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Leave a group."""
    res = await session.execute(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == current_user.id)
    )
    member = res.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    await session.delete(member)
    await session.commit()
    return None


@router.get(
    "/{group_id}/members",
    response_model=list[GroupMemberRead],
    responses={404: {"model": ErrorResponse}},
    summary="List group members",
    description="Lists members of a group (only if current user is a member).",
    operation_id="groups_list_members",
)
async def list_group_members(
    group_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[GroupMemberRead]:
    """List group members for a group the user belongs to."""
    membership = await session.execute(
        select(GroupMember.id).where(GroupMember.group_id == group_id, GroupMember.user_id == current_user.id)
    )
    if membership.first() is None:
        raise HTTPException(status_code=404, detail="Group not found or not a member")

    res = await session.execute(
        select(GroupMember).where(GroupMember.group_id == group_id).order_by(GroupMember.joined_at.asc())
    )
    members = res.scalars().all()
    return [GroupMemberRead.model_validate(m, from_attributes=True) for m in members]
