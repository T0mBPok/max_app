from datetime import date, timedelta

import pytest

from src.exceptions import AppError
from src.models import (
    Activity,
    ActivityStatus,
    ActivityType,
    AgePreset,
    Category,
    JoinPolicy,
    User,
    now_utc,
)
from src.room.logic import create_room, join_locked, room_out
from src.schemas import RoomCreate


async def test_room_owner_age_join_and_capacity(session):
    category = Category(slug="спорт", name="Спорт")
    owner = User(display_name="Владелец", birth_date=date(2005, 1, 1), city="Томск")
    peer = User(display_name="Участник", birth_date=date(2004, 1, 1), city="Томск")
    adult = User(display_name="Взрослый", birth_date=date(1980, 1, 1), city="Томск")
    session.add_all([category, owner, peer, adult])
    await session.flush()
    activity = Activity(
        type=ActivityType.SECTION,
        title="Секция",
        category_id=category.id,
        city="Томск",
        address="У входа",
        starts_at=now_utc() + timedelta(days=1),
        status=ActivityStatus.ACTIVE,
    )
    session.add(activity)
    await session.commit()
    room = await create_room(
        session,
        owner,
        RoomCreate(
            activity_id=activity.id,
            title="Идём вместе",
            age_preset=AgePreset.YOUTH_18_24,
            capacity=2,
            join_policy=JoinPolicy.OPEN,
        ),
    )
    output = await room_out(session, room, owner)
    assert output.meeting_at == activity.starts_at
    assert output.meeting_point == activity.address
    assert output.is_owner and output.members_count == 1

    with pytest.raises(AppError) as exc:
        await join_locked(session, room.id, adult)
    assert exc.value.code == "ROOM_AGE_RESTRICTION"

    await join_locked(session, room.id, peer)
    output = await room_out(session, room, peer)
    assert output.is_full and output.free_seats == 0
