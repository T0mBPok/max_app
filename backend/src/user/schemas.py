import uuid
from datetime import date

from pydantic import BaseModel, Field, field_validator

from src.common.schemas import ORMModel


class UserCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    birth_date: date
    city: str = "Томск"
    avatar_url: str | None = None

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_in_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("birth_date не может быть в будущем")
        return value


class UserUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=200)
    birth_date: date | None = None
    city: str | None = None
    avatar_url: str | None = None

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_in_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("birth_date не может быть в будущем")
        return value


class UserOut(ORMModel):
    id: uuid.UUID
    external_id: str | None
    display_name: str
    birth_date: date
    city: str
    avatar_url: str | None
