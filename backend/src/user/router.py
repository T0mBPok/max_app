from fastapi import APIRouter
from sqlalchemy import select

from src.classifiers.enums import MemberStatus
from src.config import get_settings
from src.exceptions import AppError
from src.room.logic import room_out
from src.room.models import Room, RoomMember
from src.room.schemas import RoomOut
from src.user.dependencies import CurrentUser, SessionDep
from src.user.models import User
from src.user.schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(tags=["users"])


@router.post(
    "/dev/users", response_model=UserOut, status_code=201, summary="Создать тестового пользователя"
)
async def create_user(data: UserCreate, session: SessionDep):
    if not get_settings().debug_auth_enabled:
        raise AppError("FORBIDDEN", "Endpoint отключён", 403)
    user = User(**data.model_dump())
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/users/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.patch("/users/me", response_model=UserOut)
async def update_me(data: UserUpdate, user: CurrentUser, session: SessionDep):
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/users/me/rooms", response_model=list[RoomOut])
async def my_rooms(user: CurrentUser, session: SessionDep):
    rooms = (
        await session.scalars(
            select(Room)
            .join(RoomMember)
            .where(RoomMember.user_id == user.id, RoomMember.status == MemberStatus.ACTIVE)
        )
    ).all()
    return [await room_out(session, room, user) for room in rooms]
