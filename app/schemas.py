import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import (
    ActivityStatus,
    ActivityType,
    AgePreset,
    JoinPolicy,
    JoinRequestStatus,
    RoomStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200); birth_date: date; city: str = "Томск"
    external_id: str | None = None; avatar_url: str | None = None


class UserUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=200); birth_date: date | None = None
    city: str | None = None; avatar_url: str | None = None


class UserOut(ORMModel):
    id: uuid.UUID; external_id: str | None; display_name: str; birth_date: date; city: str; avatar_url: str | None


class CategoryOut(ORMModel): id: uuid.UUID; slug: str; name: str
class SourceOut(ORMModel): id: uuid.UUID; code: str; name: str; base_url: str; enabled: bool


class OccurrenceOut(ORMModel):
    id: uuid.UUID; activity_id: uuid.UUID; starts_at: datetime; ends_at: datetime | None
    registration_deadline: datetime | None; capacity: int | None


class ActivityOut(ORMModel):
    id: uuid.UUID; type: ActivityType; title: str; short_description: str | None; description: str | None
    category_id: uuid.UUID; venue_id: uuid.UUID | None; city: str; address: str | None
    price_from: Decimal | None; price_to: Decimal | None; is_free: bool | None
    audience_min_age: int | None; audience_max_age: int | None; image_url: str | None
    registration_url: str | None; schedule_text: str | None; status: ActivityStatus


class Page(BaseModel):
    items: list; page: int; page_size: int; total: int


class RoomCreate(BaseModel):
    activity_id: uuid.UUID; occurrence_id: uuid.UUID | None = None; title: str = Field(min_length=1, max_length=250)
    description: str | None = None; age_preset: AgePreset; min_age: int | None = None; max_age: int | None = None
    capacity: int = Field(ge=2, le=20); join_policy: JoinPolicy = JoinPolicy.OPEN
    meeting_at: datetime; meeting_point: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def timezone_required(self):
        if self.meeting_at.tzinfo is None:
            raise ValueError("meeting_at должен содержать часовой пояс")
        return self


class RoomUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=250); description: str | None = None
    capacity: int | None = Field(None, ge=2, le=20); meeting_at: datetime | None = None
    meeting_point: str | None = None


class RoomOut(ORMModel):
    id: uuid.UUID; activity_id: uuid.UUID; occurrence_id: uuid.UUID | None; owner_id: uuid.UUID
    title: str; description: str | None; age_preset: AgePreset; min_age: int; max_age: int | None
    capacity: int; join_policy: JoinPolicy; status: RoomStatus; meeting_at: datetime; meeting_point: str
    members_count: int; free_seats: int; is_full: bool; is_owner: bool; is_member: bool
    is_eligible: bool; ineligible_reason: str | None; age_label: str


class JoinRequestCreate(BaseModel): message: str | None = Field(None, max_length=1000)
class JoinRequestOut(ORMModel):
    id: uuid.UUID; room_id: uuid.UUID; user_id: uuid.UUID; status: JoinRequestStatus
    message: str | None; created_at: datetime; resolved_at: datetime | None; resolved_by_id: uuid.UUID | None


class ImportRunOut(ORMModel):
    id: uuid.UUID; source_id: uuid.UUID; status: str; started_at: datetime; finished_at: datetime | None
    received_count: int; created_count: int; updated_count: int; unchanged_count: int
    skipped_count: int; error_count: int; error_message: str | None

