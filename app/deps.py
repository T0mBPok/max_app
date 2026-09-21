import uuid
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.errors import AppError
from app.models import User, UserStatus

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def current_user(session: SessionDep, x_debug_user_id: Annotated[str | None, Header()] = None) -> User:
    if not get_settings().debug_auth_enabled:
        raise AppError("FORBIDDEN", "Отладочная аутентификация отключена", 403)
    try:
        user_id = uuid.UUID(x_debug_user_id or "")
    except ValueError as exc:
        raise AppError("FORBIDDEN", "Укажите X-Debug-User-Id", 401) from exc
    user = await session.get(User, user_id)
    if not user or user.status != UserStatus.ACTIVE:
        raise AppError("FORBIDDEN", "Пользователь не найден или заблокирован", 401)
    return user


CurrentUser = Annotated[User, Depends(current_user)]
