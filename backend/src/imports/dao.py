from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.imports.models import Source, SourceRecord


async def get_source_by_code(session: AsyncSession, code: str) -> Source | None:
    return await session.scalar(select(Source).where(Source.code == code))


async def get_source_record(
    session: AsyncSession, source_id, external_id: str
) -> SourceRecord | None:
    return await session.scalar(
        select(SourceRecord).where(
            SourceRecord.source_id == source_id,
            SourceRecord.external_id == external_id,
        )
    )
