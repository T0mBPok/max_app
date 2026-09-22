import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.classifiers.enums import ActivityStatus, ActivityType
from src.common.models import TimestampMixin
from src.database import Base


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(150))


class Venue(TimestampMixin, Base):
    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(250))
    city: Mapped[str] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(500))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))


class Activity(TimestampMixin, Base):
    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[ActivityType] = mapped_column(Enum(ActivityType), index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    short_description: Mapped[str | None] = mapped_column(String(1000))
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), index=True)
    venue_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("venues.id"))
    city: Mapped[str] = mapped_column(String(100), index=True)
    address: Mapped[str | None] = mapped_column(String(500))
    price_from: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    price_to: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    is_free: Mapped[bool | None] = mapped_column(Boolean)
    audience_min_age: Mapped[int | None] = mapped_column(Integer)
    audience_max_age: Mapped[int | None] = mapped_column(Integer)
    image_url: Mapped[str | None] = mapped_column(String(1000))
    registration_url: Mapped[str | None] = mapped_column(String(1000))
    schedule_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ActivityStatus] = mapped_column(
        Enum(ActivityStatus), default=ActivityStatus.ACTIVE, index=True
    )
    occurrences: Mapped[list["ActivityOccurrence"]] = relationship(cascade="all, delete-orphan")


class ActivityOccurrence(TimestampMixin, Base):
    __tablename__ = "activity_occurrences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), index=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int | None] = mapped_column(Integer)
