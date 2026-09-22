import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from src.classifiers.enums import (
    AgePreset,
    JoinPolicy,
    JoinRequestStatus,
    RoomStatus,
)
from src.common.schemas import ORMModel


class RoomCreate(BaseModel):
    activity_id: uuid.UUID
    occurrence_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=250)
    description: str | None = None
    age_preset: AgePreset
    min_age: int | None = None
    max_age: int | None = None
    capacity: int = Field(ge=2, le=20)
    join_policy: JoinPolicy = JoinPolicy.OPEN
    meeting_at: datetime
    meeting_point: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def timezone_required(self):
        if self.meeting_at.tzinfo is None:
            raise ValueError("meeting_at должен содержать часовой пояс")
        return self


class RoomUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=250)
    description: str | None = None
    capacity: int | None = Field(None, ge=2, le=20)
    meeting_at: datetime | None = None
    meeting_point: str | None = None

    @model_validator(mode="after")
    def timezone_required(self):
        if self.meeting_at is not None and self.meeting_at.tzinfo is None:
            raise ValueError("meeting_at должен содержать часовой пояс")
        return self


class RoomOut(ORMModel):
    id: uuid.UUID
    activity_id: uuid.UUID
    occurrence_id: uuid.UUID | None
    owner_id: uuid.UUID
    title: str
    description: str | None
    age_preset: AgePreset
    min_age: int
    max_age: int | None
    capacity: int
    join_policy: JoinPolicy
    status: RoomStatus
    meeting_at: datetime
    meeting_point: str
    members_count: int
    free_seats: int
    is_full: bool
    is_owner: bool
    is_member: bool
    is_eligible: bool
    ineligible_reason: str | None
    age_label: str


class JoinRequestCreate(BaseModel):
    message: str | None = Field(None, max_length=1000)


class JoinRequestOut(ORMModel):
    id: uuid.UUID
    room_id: uuid.UUID
    user_id: uuid.UUID
    status: JoinRequestStatus
    message: str | None
    created_at: datetime
    resolved_at: datetime | None
    resolved_by_id: uuid.UUID | None
