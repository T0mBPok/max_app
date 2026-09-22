import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.classifiers.enums import MemberStatus
from src.room.models import Room, RoomMember


async def get_room(
    session: AsyncSession, room_id: uuid.UUID, *, for_update: bool = False
) -> Room | None:
    query = select(Room).where(Room.id == room_id)
    return await session.scalar(query.with_for_update() if for_update else query)


async def get_member(
    session: AsyncSession,
    room_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    only_active: bool = False,
) -> RoomMember | None:
    query = select(RoomMember).where(
        RoomMember.room_id == room_id,
        RoomMember.user_id == user_id,
    )
    if only_active:
        query = query.where(RoomMember.status == MemberStatus.ACTIVE)
    return await session.scalar(query)


async def active_members_count(session: AsyncSession, room_id: uuid.UUID) -> int:
    value = await session.scalar(
        select(func.count())
        .select_from(RoomMember)
        .where(
            RoomMember.room_id == room_id,
            RoomMember.status == MemberStatus.ACTIVE,
        )
    )
    return value or 0
