import uuid
from datetime import datetime
from decimal import Decimal

from src.classifiers.enums import ActivityStatus, ActivityType
from src.common.schemas import ORMModel


class CategoryOut(ORMModel):
    id: uuid.UUID
    slug: str
    name: str


class SourceOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    base_url: str
    enabled: bool


class OccurrenceOut(ORMModel):
    id: uuid.UUID
    activity_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime | None
    registration_deadline: datetime | None
    capacity: int | None


class ActivityOut(ORMModel):
    id: uuid.UUID
    type: ActivityType
    title: str
    short_description: str | None
    description: str | None
    category_id: uuid.UUID
    venue_id: uuid.UUID | None
    city: str
    address: str | None
    price_from: Decimal | None
    price_to: Decimal | None
    is_free: bool | None
    audience_min_age: int | None
    audience_max_age: int | None
    image_url: str | None
    registration_url: str | None
    schedule_text: str | None
    status: ActivityStatus
