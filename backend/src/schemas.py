"""Совместимый фасад; схемы определены внутри предметных модулей."""

from src.activity.schemas import ActivityOut, CategoryOut, SourceOut
from src.common.schemas import ORMModel, Page
from src.imports.schemas import ImportRunOut
from src.room.schemas import JoinRequestCreate, JoinRequestOut, RoomCreate, RoomOut, RoomUpdate
from src.user.schemas import UserCreate, UserOut, UserUpdate

__all__ = [
    "ActivityOut",
    "CategoryOut",
    "ImportRunOut",
    "JoinRequestCreate",
    "JoinRequestOut",
    "ORMModel",
    "Page",
    "RoomCreate",
    "RoomOut",
    "RoomUpdate",
    "SourceOut",
    "UserCreate",
    "UserOut",
    "UserUpdate",
]
