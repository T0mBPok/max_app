import enum
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


class StrEnum(enum.StrEnum):
    pass


class ActivityType(StrEnum):
    EVENT = "EVENT"; SECTION = "SECTION"; COURSE = "COURSE"; VOLUNTEERING = "VOLUNTEERING"


class ActivityStatus(StrEnum):
    ACTIVE = "ACTIVE"; STALE = "STALE"; ARCHIVED = "ARCHIVED"; CANCELLED = "CANCELLED"


class UserStatus(StrEnum): ACTIVE = "ACTIVE"; BLOCKED = "BLOCKED"
class ImportStatus(StrEnum): RUNNING = "RUNNING"; SUCCESS = "SUCCESS"; PARTIAL_SUCCESS = "PARTIAL_SUCCESS"; FAILED = "FAILED"
class AgePreset(StrEnum):
    TEENS_12_17 = "TEENS_12_17"; YOUTH_18_24 = "YOUTH_18_24"; ADULTS_25_39 = "ADULTS_25_39"
    ADULTS_40_59 = "ADULTS_40_59"; SENIORS_60_PLUS = "SENIORS_60_PLUS"
    ALL_ADULTS_18_PLUS = "ALL_ADULTS_18_PLUS"; CUSTOM = "CUSTOM"
class JoinPolicy(StrEnum): OPEN = "OPEN"; REQUEST_APPROVAL = "REQUEST_APPROVAL"
class RoomStatus(StrEnum): OPEN = "OPEN"; FULL = "FULL"; CLOSED = "CLOSED"; CANCELLED = "CANCELLED"; COMPLETED = "COMPLETED"
class MemberRole(StrEnum): OWNER = "OWNER"; MEMBER = "MEMBER"
class MemberStatus(StrEnum): ACTIVE = "ACTIVE"; LEFT = "LEFT"; REMOVED = "REMOVED"
class JoinRequestStatus(StrEnum): PENDING = "PENDING"; APPROVED = "APPROVED"; REJECTED = "REJECTED"; CANCELLED = "CANCELLED"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    birth_date: Mapped[date] = mapped_column(Date)
    city: Mapped[str] = mapped_column(String(100), default="Томск")
    avatar_url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.ACTIVE)


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(150))


class Venue(TimestampMixin, Base):
    __tablename__ = "venues"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(250)); city: Mapped[str] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(500))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6)); longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))


class Activity(TimestampMixin, Base):
    __tablename__ = "activities"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[ActivityType] = mapped_column(Enum(ActivityType), index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    short_description: Mapped[str | None] = mapped_column(String(1000)); description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), index=True)
    venue_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("venues.id"))
    city: Mapped[str] = mapped_column(String(100), index=True); address: Mapped[str | None] = mapped_column(String(500))
    price_from: Mapped[Decimal | None] = mapped_column(Numeric(12, 2)); price_to: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    is_free: Mapped[bool | None] = mapped_column(Boolean); audience_min_age: Mapped[int | None] = mapped_column(Integer)
    audience_max_age: Mapped[int | None] = mapped_column(Integer); image_url: Mapped[str | None] = mapped_column(String(1000))
    registration_url: Mapped[str | None] = mapped_column(String(1000)); schedule_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ActivityStatus] = mapped_column(Enum(ActivityStatus), default=ActivityStatus.ACTIVE, index=True)
    occurrences: Mapped[list["ActivityOccurrence"]] = relationship(cascade="all, delete-orphan")


class ActivityOccurrence(TimestampMixin, Base):
    __tablename__ = "activity_occurrences"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); registration_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    capacity: Mapped[int | None] = mapped_column(Integer)


class Source(TimestampMixin, Base):
    __tablename__ = "sources"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True); name: Mapped[str] = mapped_column(String(200))
    base_url: Mapped[str] = mapped_column(String(1000)); enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_successful_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceRecord(Base):
    __tablename__ = "source_records"; __table_args__ = (UniqueConstraint("source_id", "external_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id")); activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id"))
    external_id: Mapped[str] = mapped_column(String(500)); source_url: Mapped[str] = mapped_column(String(1500))
    raw_payload: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql")); content_hash: Mapped[str] = mapped_column(String(64))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ImportRun(Base):
    __tablename__ = "import_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id")); status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc); finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_count: Mapped[int] = mapped_column(default=0); created_count: Mapped[int] = mapped_column(default=0)
    updated_count: Mapped[int] = mapped_column(default=0); unchanged_count: Mapped[int] = mapped_column(default=0)
    skipped_count: Mapped[int] = mapped_column(default=0); error_count: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text)


class Room(TimestampMixin, Base):
    __tablename__ = "rooms"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id"), index=True)
    occurrence_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("activity_occurrences.id")); owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(250)); description: Mapped[str | None] = mapped_column(Text)
    age_preset: Mapped[AgePreset] = mapped_column(Enum(AgePreset)); min_age: Mapped[int] = mapped_column(Integer); max_age: Mapped[int | None] = mapped_column(Integer)
    capacity: Mapped[int] = mapped_column(Integer); join_policy: Mapped[JoinPolicy] = mapped_column(Enum(JoinPolicy))
    status: Mapped[RoomStatus] = mapped_column(Enum(RoomStatus), default=RoomStatus.OPEN)
    meeting_at: Mapped[datetime] = mapped_column(DateTime(timezone=True)); meeting_point: Mapped[str] = mapped_column(String(500))


class RoomMember(Base):
    __tablename__ = "room_members"; __table_args__ = (UniqueConstraint("room_id", "user_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE")); user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[MemberRole] = mapped_column(Enum(MemberRole)); status: Mapped[MemberStatus] = mapped_column(Enum(MemberStatus), default=MemberStatus.ACTIVE)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc); confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoomJoinRequest(Base):
    __tablename__ = "room_join_requests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE")); user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[JoinRequestStatus] = mapped_column(Enum(JoinRequestStatus), default=JoinRequestStatus.PENDING)
    message: Mapped[str | None] = mapped_column(String(1000)); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
