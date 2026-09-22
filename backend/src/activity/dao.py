import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.activity.models import Activity


async def get_activity(session: AsyncSession, activity_id: uuid.UUID) -> Activity | None:
    return await session.get(Activity, activity_id)
