from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.activity.models import Activity, ActivityOccurrence, Category
from src.classifiers.enums import ActivityStatus, ImportStatus
from src.common.models import now_utc
from src.config import get_settings
from src.exceptions import AppError
from src.imports.base import ActivitySourceAdapter, content_hash
from src.imports.dao import get_source_by_code, get_source_record
from src.imports.models import ImportRun, Source, SourceRecord


async def ensure_source(session: AsyncSession, adapter: ActivitySourceAdapter) -> Source:
    source = await get_source_by_code(session, adapter.source_code)
    if not source:
        source = Source(code=adapter.source_code, name=adapter.name, base_url=adapter.base_url)
        session.add(source)
        await session.flush()
    return source


async def run_import(session: AsyncSession, adapter: ActivitySourceAdapter) -> ImportRun:
    source = await ensure_source(session, adapter)
    source = await session.scalar(select(Source).where(Source.id == source.id).with_for_update())
    if not source.enabled:
        raise AppError("PARSER_SOURCE_UNAVAILABLE", "Источник отключён", 409)
    running = await session.scalar(
        select(ImportRun).where(
            ImportRun.source_id == source.id, ImportRun.status == ImportStatus.RUNNING
        )
    )
    if running:
        raise AppError("IMPORT_ALREADY_RUNNING", "Импорт этого источника уже выполняется", 409)
    run = ImportRun(source_id=source.id, status=ImportStatus.RUNNING)
    session.add(run)
    await session.commit()
    try:
        raw_items = await adapter.fetch()
        if not raw_items and not adapter.allow_empty:
            raise RuntimeError("Источник не вернул ни одной записи")
        run.received_count = len(raw_items)
        seen: set[str] = set()
        for raw in raw_items:
            savepoint = await session.begin_nested()
            try:
                item = adapter.normalize(raw)
                if not item.title or not item.external_id:
                    raise ValueError("нет обязательных полей")
                seen.add(item.external_id)
                digest = content_hash(item)
                record = await get_source_record(session, source.id, item.external_id)
                if record and record.content_hash == digest:
                    record.last_seen_at = now_utc()
                    run.unchanged_count += 1
                    await savepoint.commit()
                    continue
                category = await session.scalar(
                    select(Category).where(Category.slug == item.category_slug)
                )
                if not category:
                    category = Category(
                        slug=item.category_slug, name=item.category_slug.capitalize()
                    )
                    session.add(category)
                    await session.flush()
                values = {
                    key: getattr(item, key)
                    for key in (
                        "type",
                        "title",
                        "short_description",
                        "description",
                        "city",
                        "address",
                        "price_from",
                        "price_to",
                        "is_free",
                        "audience_min_age",
                        "audience_max_age",
                        "image_url",
                        "registration_url",
                        "schedule_text",
                    )
                }
                if record:
                    activity = await session.get(Activity, record.activity_id)
                    for key, value in values.items():
                        setattr(activity, key, value)
                    activity.category_id = category.id
                    activity.status = ActivityStatus.ACTIVE
                    record.source_url = item.source_url
                    record.raw_payload = raw
                    record.content_hash = digest
                    record.last_seen_at = now_utc()
                    record.source_updated_at = item.source_updated_at
                    run.updated_count += 1
                    if item.starts_at:
                        occurrence = await session.scalar(
                            select(ActivityOccurrence).where(
                                ActivityOccurrence.activity_id == activity.id
                            )
                        )
                        if occurrence:
                            occurrence.starts_at, occurrence.ends_at = item.starts_at, item.ends_at
                        else:
                            session.add(
                                ActivityOccurrence(
                                    activity_id=activity.id,
                                    starts_at=item.starts_at,
                                    ends_at=item.ends_at,
                                )
                            )
                else:
                    activity = None
                    if item.address or item.starts_at:
                        duplicate = select(Activity).where(
                            func.lower(Activity.title) == item.title.strip().lower(),
                            Activity.type == item.type,
                            func.lower(Activity.city) == item.city.strip().lower(),
                        )
                        if item.address:
                            duplicate = duplicate.where(Activity.address == item.address)
                        if item.starts_at:
                            duplicate = duplicate.join(ActivityOccurrence).where(
                                ActivityOccurrence.starts_at == item.starts_at
                            )
                        activity = await session.scalar(duplicate.limit(1))
                    if not activity:
                        activity = Activity(
                            category_id=category.id, status=ActivityStatus.ACTIVE, **values
                        )
                        session.add(activity)
                        await session.flush()
                        if item.starts_at:
                            session.add(
                                ActivityOccurrence(
                                    activity_id=activity.id,
                                    starts_at=item.starts_at,
                                    ends_at=item.ends_at,
                                )
                            )
                        run.created_count += 1
                    else:
                        run.unchanged_count += 1
                    session.add(
                        SourceRecord(
                            source_id=source.id,
                            activity_id=activity.id,
                            external_id=item.external_id,
                            source_url=item.source_url,
                            raw_payload=raw,
                            content_hash=digest,
                            source_updated_at=item.source_updated_at,
                        )
                    )
                await session.flush()
                await savepoint.commit()
            except Exception:
                await savepoint.rollback()
                run.error_count += 1
                run.skipped_count += 1
        cutoff = now_utc() - timedelta(days=get_settings().stale_after_days)
        old_records = (
            await session.scalars(
                select(SourceRecord).where(
                    SourceRecord.source_id == source.id, SourceRecord.last_seen_at < cutoff
                )
            )
        ).all()
        for record in old_records:
            if record.external_id not in seen:
                activity = await session.get(Activity, record.activity_id)
                activity.status = ActivityStatus.STALE
        run.status = ImportStatus.PARTIAL_SUCCESS if run.error_count else ImportStatus.SUCCESS
        run.finished_at = now_utc()
        source.last_successful_run_at = now_utc()
        await session.commit()
    except Exception as exc:
        run.status = ImportStatus.FAILED
        run.finished_at = now_utc()
        run.error_message = str(exc)[:2000]
        await session.commit()
        raise AppError("PARSER_SOURCE_UNAVAILABLE", "Источник временно недоступен", 503) from exc
    return run
