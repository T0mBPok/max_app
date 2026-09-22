from datetime import timedelta

from sqlalchemy import func, select

from src.imports.base import ActivitySourceAdapter, NormalizedActivity
from src.imports.logic import run_import
from src.models import Activity, ActivityStatus, ActivityType, SourceRecord, now_utc


class FakeAdapter(ActivitySourceAdapter):
    source_code = "fake"
    name = "Fixture"
    base_url = "https://example.test"
    allow_empty = True

    def __init__(self):
        self.items = [{"id": "1", "title": "Кружок"}]

    async def fetch(self):
        return self.items

    def normalize(self, item):
        if "title" not in item:
            raise ValueError("bad fixture")
        return NormalizedActivity(
            external_id=item["id"],
            source_url=f"{self.base_url}/{item['id']}",
            type=ActivityType.SECTION,
            title=item["title"],
            category_slug="образование",
            schedule_text="Пн 18:00",
            raw_payload=item,
        )


async def test_import_is_idempotent_updates_and_isolates_bad_records(session):
    adapter = FakeAdapter()
    first = await run_import(session, adapter)
    assert first.created_count == 1
    assert await session.scalar(select(func.count()).select_from(Activity)) == 1

    second = await run_import(session, adapter)
    assert second.unchanged_count == 1
    assert await session.scalar(select(func.count()).select_from(Activity)) == 1

    adapter.items = [{"id": "1", "title": "Новый кружок"}, {"id": "bad"}]
    third = await run_import(session, adapter)
    assert (third.updated_count, third.error_count) == (1, 1)
    activity = await session.scalar(select(Activity))
    assert activity.title == "Новый кружок"

    record = await session.scalar(select(SourceRecord))
    record.last_seen_at = now_utc() - timedelta(days=8)
    await session.commit()
    adapter.items = []
    await run_import(session, adapter)
    await session.refresh(activity)
    assert activity.status == ActivityStatus.STALE
