import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.activity.dao import get_activity
from src.activity.models import Venue
from src.classifiers.enums import ActivityStatus, JoinPolicy, MemberRole, MemberStatus, RoomStatus
from src.common.age import (
    build_age_label,
    calculate_age,
    is_age_eligible,
    resolve_age_range,
    today_tomsk,
    validate_age_range,
)
from src.common.models import now_utc
from src.exceptions import AppError, not_found
from src.room.dao import active_members_count, get_member, get_room
from src.room.models import Room, RoomMember
from src.room.schemas import RoomCreate, RoomOut, RoomUpdate
from src.user.models import User


def eligibility(room: Room, user: User) -> tuple[bool, str | None]:
    age = calculate_age(user.birth_date, today_tomsk())
    if not is_age_eligible(age, room.min_age, room.max_age):
        return False, "Ваш возраст не соответствует возрастной группе комнаты"
    return True, None


async def room_out(session: AsyncSession, room: Room, user: User) -> RoomOut:
    count = await active_members_count(session, room.id)
    member = await get_member(session, room.id, user.id, only_active=True)
    eligible, reason = eligibility(room, user)
    activity = await get_activity(session, room.activity_id)
    venue = await session.get(Venue, activity.venue_id) if activity and activity.venue_id else None
    meeting_point = activity.address if activity else None
    if not meeting_point and venue:
        meeting_point = venue.address or venue.name
    return RoomOut.model_validate(
        {
            **{c.name: getattr(room, c.name) for c in room.__table__.columns},
            "meeting_at": activity.starts_at if activity else None,
            "meeting_point": meeting_point,
            "members_count": count,
            "free_seats": max(room.capacity - count, 0),
            "is_full": count >= room.capacity,
            "is_owner": room.owner_id == user.id,
            "is_member": member is not None,
            "is_eligible": eligible,
            "ineligible_reason": reason,
            "age_label": build_age_label(room.min_age, room.max_age, room.age_preset),
        }
    )


async def create_room(
    session: AsyncSession,
    user: User,
    data: RoomCreate,
) -> Room:
    activity = await get_activity(session, data.activity_id)

    if not activity:
        raise not_found(
            "ACTIVITY_NOT_FOUND",
            "Активность не найдена",
        )

    if activity.status in {
        ActivityStatus.ARCHIVED,
        ActivityStatus.CANCELLED,
    }:
        raise AppError(
            "ROOM_CLOSED",
            "Для этой активности нельзя создать комнату",
            409,
        )

    min_age, max_age = resolve_age_range(
        data.age_preset,
        data.min_age,
        data.max_age,
    )
    if min_age is not None:
        validate_age_range(min_age, max_age)

    age = calculate_age(
        user.birth_date,
        today_tomsk(),
    )

    if not is_age_eligible(age, min_age, max_age):
        raise AppError(
            "ROOM_AGE_RESTRICTION",
            "Возраст создателя не соответствует комнате",
            403,
        )

    if activity.audience_min_age is not None and (
        min_age is None or min_age < activity.audience_min_age
    ):
        raise AppError(
            "INVALID_AGE_RANGE",
            "Диапазон комнаты шире ограничений активности",
        )

    if activity.audience_max_age is not None and (
        max_age is None or max_age > activity.audience_max_age
    ):
        raise AppError(
            "INVALID_AGE_RANGE",
            "Диапазон комнаты шире ограничений активности",
        )

    current_time = now_utc()
    if not activity.starts_at:
        raise AppError(
            "ACTIVITY_TIME_NOT_FOUND",
            "У активности не указано время проведения",
            409,
        )

    meeting_at = activity.starts_at.astimezone(current_time.tzinfo)
    if meeting_at <= current_time:
        raise AppError(
            "ROOM_CLOSED",
            "Мероприятие уже началось или завершилось",
            409,
        )

    venue = await session.get(Venue, activity.venue_id) if activity.venue_id else None
    meeting_point = activity.address or (venue.address if venue else None)
    if not meeting_point and venue:
        meeting_point = venue.name
    if not meeting_point:
        raise AppError(
            "ACTIVITY_LOCATION_NOT_FOUND",
            "У активности не указано место проведения",
            409,
        )

    room = Room(
        **data.model_dump(
            exclude={
                "min_age",
                "max_age",
            }
        ),
        min_age=min_age,
        max_age=max_age,
        owner_id=user.id,
    )

    session.add(room)
    await session.flush()

    session.add(
        RoomMember(
            room_id=room.id,
            user_id=user.id,
            role=MemberRole.OWNER,
            status=MemberStatus.ACTIVE,
            confirmed_at=now_utc(),
        )
    )

    await session.commit()
    await session.refresh(room)

    return room


async def update_room(session: AsyncSession, room: Room, data: RoomUpdate) -> Room:
    changes = data.model_dump(exclude_unset=True)
    if "capacity" in changes:
        members_count = await active_members_count(session, room.id)
        if changes["capacity"] < members_count:
            raise AppError("ROOM_FULL", "Вместимость меньше числа участников", 409)
        if room.status in {RoomStatus.OPEN, RoomStatus.FULL}:
            room.status = (
                RoomStatus.FULL if changes["capacity"] == members_count else RoomStatus.OPEN
            )
    for key, value in changes.items():
        setattr(room, key, value)
    await session.commit()
    await session.refresh(room)
    return room


async def join_locked(session: AsyncSession, room_id: uuid.UUID, user: User) -> Room:
    room = await get_room(session, room_id, for_update=True)
    if not room:
        raise not_found("ROOM_NOT_FOUND", "Комната не найдена")
    if room.join_policy != JoinPolicy.OPEN:
        raise AppError("FORBIDDEN", "Для комнаты требуется заявка", 409)
    return await add_member_locked(session, room, user)


async def add_member_locked(
    session: AsyncSession, room: Room, user: User, *, commit: bool = True
) -> Room:
    if room.status not in {RoomStatus.OPEN, RoomStatus.FULL}:
        raise AppError("ROOM_CLOSED", "Комната закрыта", 409)
    eligible, _ = eligibility(room, user)
    if not eligible:
        raise AppError(
            "ROOM_AGE_RESTRICTION", "Ваш возраст не соответствует возрастной группе комнаты", 403
        )
    member = await get_member(session, room.id, user.id)
    if member and member.status == MemberStatus.ACTIVE:
        raise AppError("ALREADY_ROOM_MEMBER", "Вы уже состоите в комнате", 409)
    count = await active_members_count(session, room.id)
    if count >= room.capacity:
        raise AppError("ROOM_FULL", "В комнате нет свободных мест", 409)
    if member:
        member.status = MemberStatus.ACTIVE
        member.joined_at = now_utc()
        member.confirmed_at = now_utc()
        member.role = MemberRole.MEMBER
    else:
        session.add(
            RoomMember(
                room_id=room.id,
                user_id=user.id,
                role=MemberRole.MEMBER,
                status=MemberStatus.ACTIVE,
                confirmed_at=now_utc(),
            )
        )
    if count + 1 >= room.capacity:
        room.status = RoomStatus.FULL
    if commit:
        await session.commit()
    else:
        await session.flush()
    return room
