import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.age import (
    build_age_label,
    calculate_age,
    is_age_eligible,
    resolve_age_range,
    validate_age_range,
)
from app.errors import AppError, not_found
from app.models import (
    Activity,
    ActivityOccurrence,
    ActivityStatus,
    JoinPolicy,
    MemberRole,
    MemberStatus,
    Room,
    RoomMember,
    RoomStatus,
    User,
    now_utc,
)
from app.schemas import RoomCreate, RoomOut


def eligibility(room: Room, user: User) -> tuple[bool, str | None]:
    age = calculate_age(user.birth_date, date.today())
    if not is_age_eligible(age, room.min_age, room.max_age):
        return False, "Ваш возраст не соответствует возрастной группе комнаты"
    return True, None


async def room_out(session: AsyncSession, room: Room, user: User) -> RoomOut:
    count = await session.scalar(select(func.count()).select_from(RoomMember).where(RoomMember.room_id == room.id, RoomMember.status == MemberStatus.ACTIVE)) or 0
    member = await session.scalar(select(RoomMember).where(RoomMember.room_id == room.id, RoomMember.user_id == user.id, RoomMember.status == MemberStatus.ACTIVE))
    eligible, reason = eligibility(room, user)
    return RoomOut.model_validate({**{c.name: getattr(room, c.name) for c in room.__table__.columns},
        "members_count": count, "free_seats": max(room.capacity - count, 0), "is_full": count >= room.capacity,
        "is_owner": room.owner_id == user.id, "is_member": member is not None, "is_eligible": eligible,
        "ineligible_reason": reason, "age_label": build_age_label(room.min_age, room.max_age, room.age_preset)})


async def create_room(session: AsyncSession, user: User, data: RoomCreate) -> Room:
    activity = await session.get(Activity, data.activity_id)
    if not activity: raise not_found("ACTIVITY_NOT_FOUND", "Активность не найдена")
    if activity.status in {ActivityStatus.ARCHIVED, ActivityStatus.CANCELLED}:
        raise AppError("ROOM_CLOSED", "Для этой активности нельзя создать комнату", 409)
    min_age, max_age = resolve_age_range(data.age_preset, data.min_age, data.max_age); validate_age_range(min_age, max_age)
    age = calculate_age(user.birth_date, date.today())
    if not is_age_eligible(age, min_age, max_age): raise AppError("ROOM_AGE_RESTRICTION", "Возраст создателя не соответствует комнате", 403)
    if activity.audience_min_age is not None and min_age < activity.audience_min_age: raise AppError("INVALID_AGE_RANGE", "Диапазон комнаты шире ограничений активности")
    if activity.audience_max_age is not None and (max_age is None or max_age > activity.audience_max_age): raise AppError("INVALID_AGE_RANGE", "Диапазон комнаты шире ограничений активности")
    meeting_at = data.meeting_at.astimezone(now_utc().tzinfo)
    if meeting_at <= now_utc(): raise AppError("ROOM_CLOSED", "Время встречи уже прошло")
    if data.occurrence_id:
        occurrence = await session.get(ActivityOccurrence, data.occurrence_id)
        if not occurrence or occurrence.activity_id != activity.id: raise AppError("ACTIVITY_NOT_FOUND", "Дата активности не найдена", 404)
        if meeting_at > occurrence.starts_at: raise AppError("ROOM_CLOSED", "Встреча должна быть до начала события")
    room = Room(**data.model_dump(exclude={"min_age", "max_age"}), min_age=min_age, max_age=max_age, owner_id=user.id)
    session.add(room); await session.flush()
    session.add(RoomMember(room_id=room.id, user_id=user.id, role=MemberRole.OWNER, status=MemberStatus.ACTIVE, confirmed_at=now_utc()))
    await session.commit(); await session.refresh(room); return room


async def join_locked(session: AsyncSession, room_id: uuid.UUID, user: User) -> Room:
    room = await session.scalar(select(Room).where(Room.id == room_id).with_for_update())
    if not room: raise not_found("ROOM_NOT_FOUND", "Комната не найдена")
    if room.join_policy != JoinPolicy.OPEN: raise AppError("FORBIDDEN", "Для комнаты требуется заявка", 409)
    return await add_member_locked(session, room, user)


async def add_member_locked(
    session: AsyncSession, room: Room, user: User, *, commit: bool = True
) -> Room:
    if room.status not in {RoomStatus.OPEN, RoomStatus.FULL}: raise AppError("ROOM_CLOSED", "Комната закрыта", 409)
    eligible, _ = eligibility(room, user)
    if not eligible: raise AppError("ROOM_AGE_RESTRICTION", "Ваш возраст не соответствует возрастной группе комнаты", 403)
    member = await session.scalar(select(RoomMember).where(RoomMember.room_id == room.id, RoomMember.user_id == user.id))
    if member and member.status == MemberStatus.ACTIVE: raise AppError("ALREADY_ROOM_MEMBER", "Вы уже состоите в комнате", 409)
    count = await session.scalar(select(func.count()).select_from(RoomMember).where(RoomMember.room_id == room.id, RoomMember.status == MemberStatus.ACTIVE)) or 0
    if count >= room.capacity: raise AppError("ROOM_FULL", "В комнате нет свободных мест", 409)
    if member:
        member.status = MemberStatus.ACTIVE; member.joined_at = now_utc(); member.confirmed_at = now_utc(); member.role = MemberRole.MEMBER
    else: session.add(RoomMember(room_id=room.id, user_id=user.id, role=MemberRole.MEMBER, status=MemberStatus.ACTIVE, confirmed_at=now_utc()))
    if count + 1 >= room.capacity: room.status = RoomStatus.FULL
    if commit:
        await session.commit()
    else:
        await session.flush()
    return room
