import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.user.models import User


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)
