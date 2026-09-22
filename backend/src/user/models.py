import uuid
from datetime import date

from sqlalchemy import Date, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.classifiers.enums import UserStatus
from src.common.models import TimestampMixin
from src.database import Base


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    birth_date: Mapped[date] = mapped_column(Date)
    city: Mapped[str] = mapped_column(String(100), default="Томск")
    avatar_url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.ACTIVE)
