"""Единая точка регистрации ORM-моделей для Alembic."""

from src.activity.models import Activity, Category, Venue
from src.imports.models import ImportRun, Source, SourceRecord
from src.room.models import Room, RoomJoinRequest, RoomMember
from src.user.models import User

__all__ = [
    "Activity",
    "Category",
    "ImportRun",
    "Room",
    "RoomJoinRequest",
    "RoomMember",
    "Source",
    "SourceRecord",
    "User",
    "Venue",
]
