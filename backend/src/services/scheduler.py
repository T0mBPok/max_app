import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.config import get_settings
from src.database import SessionLocal
from src.imports.logic import run_import
from src.imports.registry import adapters

logger = logging.getLogger(__name__)


async def import_all():
    async with SessionLocal() as session:
        for adapter in adapters.values():
            try:
                await run_import(session, adapter)
            except Exception:
                logger.exception("Import failed for source %s", adapter.source_code)


async def main():
    if not get_settings().parser_scheduler_enabled:
        while True:
            await asyncio.sleep(3600)
    scheduler = AsyncIOScheduler(timezone="Asia/Tomsk")
    scheduler.add_job(import_all, "cron", hour=3, id="daily-import", max_instances=1)
    scheduler.start()
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
