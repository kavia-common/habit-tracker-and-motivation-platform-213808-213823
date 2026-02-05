from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Human-readable error message")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")


class UserPublic(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    created_at: dt.datetime


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="User email (unique)")
    password: str = Field(..., min_length=8, description="User password (min 8 chars)")
    display_name: str = Field(..., min_length=1, max_length=120, description="Display name")


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., description="User password")


ScheduleType = Literal["daily", "weekly"]


class HabitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Habit name")
    description: str | None = Field(None, description="Habit description")
    schedule_type: ScheduleType = Field("daily", description="Schedule type: daily or weekly")
    target_per_period: int = Field(1, ge=1, le=1000, description="Target count per period")
    is_active: bool = Field(True, description="Whether habit is active")


class HabitUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = None
    schedule_type: ScheduleType | None = None
    target_per_period: int | None = Field(None, ge=1, le=1000)
    is_active: bool | None = None


class HabitRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None
    schedule_type: ScheduleType
    target_per_period: int
    is_active: bool
    created_at: dt.datetime


class CheckInCreate(BaseModel):
    checkin_date: dt.date = Field(..., description="Date for the check-in (YYYY-MM-DD)")
    count: int = Field(1, ge=1, le=1000, description="How many times completed on the date")
    note: str | None = Field(None, description="Optional note")


class CheckInRead(BaseModel):
    id: uuid.UUID
    habit_id: uuid.UUID
    user_id: uuid.UUID
    checkin_date: dt.date
    count: int
    note: str | None
    created_at: dt.datetime


class StreakInfo(BaseModel):
    current_streak_days: int = Field(..., ge=0)
    longest_streak_days: int = Field(..., ge=0)
    last_checkin_date: dt.date | None


class HabitWithStats(BaseModel):
    habit: HabitRead
    streak: StreakInfo
    completed_today: bool
    completed_this_week: bool


class DashboardSummary(BaseModel):
    active_habits: int = Field(..., ge=0)
    checkins_last_7_days: int = Field(..., ge=0)
    current_best_streak: int = Field(..., ge=0)
    achievements_count: int = Field(..., ge=0)


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None


class GroupRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_by_user_id: uuid.UUID | None
    created_at: dt.datetime


class GroupMemberRead(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    joined_at: dt.datetime


class AchievementRead(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str
    icon: str | None
    created_at: dt.datetime


class UserAchievementRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    achievement_id: uuid.UUID
    awarded_at: dt.datetime
    achievement: AchievementRead


class ActivityEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    event_type: str
    message: str
    created_at: dt.datetime
