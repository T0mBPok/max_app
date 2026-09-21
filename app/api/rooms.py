import uuid
from datetime import date

from fastapi import APIRouter, Query, Response
from sqlalchemy import func, select

from app.age import calculate_age
from app.deps import CurrentUser, SessionDep
from app.errors import AppError, not_found
from app.models import (
    AgePreset,
    JoinPolicy,
    JoinRequestStatus,
    MemberStatus,
    Room,
    RoomJoinRequest,
    RoomMember,
    RoomStatus,
    now_utc,
)
from app.room_service import add_member_locked, create_room, eligibility, join_locked, room_out
from app.schemas import JoinRequestCreate, JoinRequestOut, RoomCreate, RoomOut, RoomUpdate

router = APIRouter(prefix="/rooms", tags=["rooms"])


async def get_room(session: SessionDep, room_id: uuid.UUID, lock: bool = False) -> Room:
    stmt = select(Room).where(Room.id == room_id)
    room = await session.scalar(stmt.with_for_update() if lock else stmt)
    if not room: raise not_found("ROOM_NOT_FOUND", "Комната не найдена")
    return room


def owner_only(room: Room, user_id: uuid.UUID) -> None:
    if room.owner_id != user_id: raise AppError("FORBIDDEN", "Действие доступно только владельцу", 403)


@router.post("", response_model=RoomOut, status_code=201)
async def create(data: RoomCreate, user: CurrentUser, session: SessionDep):
    return await room_out(session, await create_room(session, user, data), user)


@router.get("", response_model=dict)
async def list_rooms(user: CurrentUser, session: SessionDep, activity_id: uuid.UUID | None = None,
    occurrence_id: uuid.UUID | None = None, city: str | None = None, status: RoomStatus | None = None,
    age_preset: AgePreset | None = None, has_free_seats: bool | None = None, eligible_for_me: bool = True,
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    stmt = select(Room)
    if activity_id: stmt = stmt.where(Room.activity_id == activity_id)
    if occurrence_id: stmt = stmt.where(Room.occurrence_id == occurrence_id)
    if status: stmt = stmt.where(Room.status == status)
    if age_preset: stmt = stmt.where(Room.age_preset == age_preset)
    if city:
        from app.models import Activity
        stmt = stmt.join(Activity).where(func.lower(Activity.city) == city.lower())
    age = calculate_age(user.birth_date, date.today())
    if eligible_for_me: stmt = stmt.where(Room.min_age <= age).where((Room.max_age.is_(None)) | (Room.max_age >= age))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rooms = (await session.scalars(stmt.offset((page - 1) * page_size).limit(page_size))).all()
    output = [await room_out(session, room, user) for room in rooms]
    if has_free_seats is not None: output = [x for x in output if (x.free_seats > 0) == has_free_seats]
    return {"items": output, "page": page, "page_size": page_size, "total": total}


@router.get("/{room_id}", response_model=RoomOut)
async def detail(room_id: uuid.UUID, user: CurrentUser, session: SessionDep): return await room_out(session, await get_room(session, room_id), user)


@router.patch("/{room_id}", response_model=RoomOut)
async def update(room_id: uuid.UUID, data: RoomUpdate, user: CurrentUser, session: SessionDep):
    room = await get_room(session, room_id); owner_only(room, user.id)
    for key, value in data.model_dump(exclude_unset=True).items(): setattr(room, key, value)
    await session.commit(); return await room_out(session, room, user)


@router.delete("/{room_id}", status_code=204)
async def delete(room_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    room = await get_room(session, room_id); owner_only(room, user.id); room.status = RoomStatus.CANCELLED
    await session.commit(); return Response(status_code=204)


@router.post("/{room_id}/join", response_model=RoomOut)
async def join(room_id: uuid.UUID, user: CurrentUser, session: SessionDep): return await room_out(session, await join_locked(session, room_id, user), user)


@router.post("/{room_id}/leave", response_model=RoomOut)
async def leave(room_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    room = await get_room(session, room_id, True)
    if room.owner_id == user.id: raise AppError("FORBIDDEN", "Владелец не может покинуть комнату", 403)
    member = await session.scalar(select(RoomMember).where(RoomMember.room_id == room.id, RoomMember.user_id == user.id, RoomMember.status == MemberStatus.ACTIVE))
    if not member: raise AppError("FORBIDDEN", "Вы не состоите в комнате", 409)
    member.status = MemberStatus.LEFT
    if room.status == RoomStatus.FULL: room.status = RoomStatus.OPEN
    await session.commit(); return await room_out(session, room, user)


async def set_status(room_id: uuid.UUID, status: RoomStatus, user, session):
    room = await get_room(session, room_id); owner_only(room, user.id); room.status = status; await session.commit()
    return await room_out(session, room, user)


@router.post("/{room_id}/close", response_model=RoomOut)
async def close(room_id: uuid.UUID, user: CurrentUser, session: SessionDep): return await set_status(room_id, RoomStatus.CLOSED, user, session)


@router.post("/{room_id}/cancel", response_model=RoomOut)
async def cancel_room(room_id: uuid.UUID, user: CurrentUser, session: SessionDep): return await set_status(room_id, RoomStatus.CANCELLED, user, session)


@router.post("/{room_id}/join-requests", response_model=JoinRequestOut, status_code=201)
async def request_join(room_id: uuid.UUID, data: JoinRequestCreate, user: CurrentUser, session: SessionDep):
    room = await get_room(session, room_id)
    if room.join_policy != JoinPolicy.REQUEST_APPROVAL: raise AppError("FORBIDDEN", "Комната открыта для прямого вступления", 409)
    if room.status != RoomStatus.OPEN: raise AppError("ROOM_CLOSED", "Комната закрыта", 409)
    if not eligibility(room, user)[0]: raise AppError("ROOM_AGE_RESTRICTION", "Ваш возраст не соответствует возрастной группе комнаты", 403)
    existing = await session.scalar(select(RoomJoinRequest).where(RoomJoinRequest.room_id == room.id, RoomJoinRequest.user_id == user.id, RoomJoinRequest.status == JoinRequestStatus.PENDING))
    if existing: raise AppError("JOIN_REQUEST_ALREADY_EXISTS", "Активная заявка уже существует", 409)
    request = RoomJoinRequest(room_id=room.id, user_id=user.id, message=data.message); session.add(request); await session.commit(); await session.refresh(request); return request


@router.get("/{room_id}/join-requests", response_model=list[JoinRequestOut])
async def requests(room_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    room = await get_room(session, room_id); owner_only(room, user.id)
    return (await session.scalars(select(RoomJoinRequest).where(RoomJoinRequest.room_id == room.id))).all()


async def resolve_request(room_id, request_id, approve, user, session):
    room = await get_room(session, room_id, approve); owner_only(room, user.id)
    request = await session.get(RoomJoinRequest, request_id)
    if not request or request.room_id != room.id or request.status != JoinRequestStatus.PENDING: raise not_found("ROOM_NOT_FOUND", "Заявка не найдена")
    if approve:
        applicant = await session.get(type(user), request.user_id)
        await add_member_locked(session, room, applicant, commit=False)
        request.status = JoinRequestStatus.APPROVED
    else: request.status = JoinRequestStatus.REJECTED
    request.resolved_at = now_utc(); request.resolved_by_id = user.id; await session.commit(); return request


@router.post("/{room_id}/join-requests/{request_id}/approve", response_model=JoinRequestOut)
async def approve(room_id: uuid.UUID, request_id: uuid.UUID, user: CurrentUser, session: SessionDep): return await resolve_request(room_id, request_id, True, user, session)


@router.post("/{room_id}/join-requests/{request_id}/reject", response_model=JoinRequestOut)
async def reject(room_id: uuid.UUID, request_id: uuid.UUID, user: CurrentUser, session: SessionDep): return await resolve_request(room_id, request_id, False, user, session)


@router.post("/{room_id}/join-requests/{request_id}/cancel", response_model=JoinRequestOut)
async def cancel_request(room_id: uuid.UUID, request_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    request = await session.get(RoomJoinRequest, request_id)
    if not request or request.room_id != room_id: raise not_found("ROOM_NOT_FOUND", "Заявка не найдена")
    if request.user_id != user.id or request.status != JoinRequestStatus.PENDING: raise AppError("FORBIDDEN", "Нельзя отменить заявку", 403)
    request.status = JoinRequestStatus.CANCELLED; request.resolved_at = now_utc(); await session.commit(); return request
