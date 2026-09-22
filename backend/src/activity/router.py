import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from src.activity.dao import get_activity
from src.activity.models import Activity, ActivityOccurrence, Category
from src.activity.schemas import ActivityOut, CategoryOut, OccurrenceOut, SourceOut
from src.classifiers.enums import ActivityStatus, ActivityType, RoomStatus
from src.common.schemas import Page
from src.exceptions import not_found
from src.imports.models import Source
from src.room.logic import room_out
from src.room.models import Room
from src.room.schemas import RoomOut
from src.user.dependencies import CurrentUser, SessionDep

router = APIRouter(tags=["activities"])


@router.get("/activities", response_model=Page[ActivityOut])
async def activities(
    session: SessionDep,
    type: ActivityType | None = None,
    category: str | None = None,
    city: str | None = None,
    min_age: int | None = None,
    max_age: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    is_free: bool | None = None,
    has_open_rooms: bool | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stmt = select(Activity).where(Activity.status == ActivityStatus.ACTIVE)
    if type:
        stmt = stmt.where(Activity.type == type)
    if category:
        stmt = stmt.join(Category).where(Category.slug == category)
    if city:
        stmt = stmt.where(func.lower(Activity.city) == city.lower())
    if min_age is not None:
        stmt = stmt.where(
            or_(Activity.audience_max_age.is_(None), Activity.audience_max_age >= min_age)
        )
    if max_age is not None:
        stmt = stmt.where(
            or_(Activity.audience_min_age.is_(None), Activity.audience_min_age <= max_age)
        )
    if is_free is not None:
        stmt = stmt.where(Activity.is_free == is_free)
    if search:
        stmt = stmt.where(
            or_(Activity.title.ilike(f"%{search}%"), Activity.description.ilike(f"%{search}%"))
        )
    if date_from or date_to:
        stmt = stmt.join(ActivityOccurrence)
        if date_from:
            stmt = stmt.where(ActivityOccurrence.starts_at >= date_from)
        if date_to:
            stmt = stmt.where(ActivityOccurrence.starts_at <= date_to)
    if has_open_rooms:
        stmt = stmt.join(Room).where(Room.status == RoomStatus.OPEN)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = (
        await session.scalars(stmt.distinct().offset((page - 1) * page_size).limit(page_size))
    ).all()
    return {
        "items": [ActivityOut.model_validate(x) for x in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.get("/activities/{activity_id}", response_model=ActivityOut)
async def activity(activity_id: uuid.UUID, session: SessionDep):
    item = await get_activity(session, activity_id)
    if not item:
        raise not_found("ACTIVITY_NOT_FOUND", "Активность не найдена")
    return item


@router.get("/activities/{activity_id}/occurrences", response_model=list[OccurrenceOut])
async def occurrences(activity_id: uuid.UUID, session: SessionDep):
    return (
        await session.scalars(
            select(ActivityOccurrence)
            .where(ActivityOccurrence.activity_id == activity_id)
            .order_by(ActivityOccurrence.starts_at)
        )
    ).all()


@router.get("/categories", response_model=list[CategoryOut])
async def categories(session: SessionDep):
    return (await session.scalars(select(Category).order_by(Category.name))).all()


@router.get("/sources", response_model=list[SourceOut])
async def sources(session: SessionDep):
    return (await session.scalars(select(Source).order_by(Source.name))).all()


@router.get("/activities/{activity_id}/rooms", response_model=list[RoomOut])
async def activity_rooms(activity_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    rooms = (await session.scalars(select(Room).where(Room.activity_id == activity_id))).all()
    return [await room_out(session, item, user) for item in rooms]
