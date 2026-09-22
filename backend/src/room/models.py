import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.classifiers.enums import (
    AgePreset,
    JoinPolicy,
    JoinRequestStatus,
    MemberRole,
    MemberStatus,
    RoomStatus,
)
from src.common.models import TimestampMixin, now_utc
from src.database import Base


class Room(TimestampMixin, Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("activities.id"), index=True)
    occurrence_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("activity_occurrences.id"))
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str | None] = mapped_column(Text)
    age_preset: Mapped[AgePreset] = mapped_column(Enum(AgePreset))
    min_age: Mapped[int] = mapped_column(Integer)
    max_age: Mapped[int | None] = mapped_column(Integer)
    capacity: Mapped[int] = mapped_column(Integer)
    join_policy: Mapped[JoinPolicy] = mapped_column(Enum(JoinPolicy))
    status: Mapped[RoomStatus] = mapped_column(Enum(RoomStatus), default=RoomStatus.OPEN)
    meeting_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    meeting_point: Mapped[str] = mapped_column(String(500))


class RoomMember(Base):
    __tablename__ = "room_members"
    __table_args__ = (UniqueConstraint("room_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[MemberRole] = mapped_column(Enum(MemberRole))
    status: Mapped[MemberStatus] = mapped_column(Enum(MemberStatus), default=MemberStatus.ACTIVE)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RoomJoinRequest(Base):
    __tablename__ = "room_join_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[JoinRequestStatus] = mapped_column(
        Enum(JoinRequestStatus), default=JoinRequestStatus.PENDING
    )
    message: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
