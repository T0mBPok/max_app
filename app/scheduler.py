import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.db import SessionLocal
from app.imports.registry import adapters
from app.imports.service import run_import


async def import_all():
    async with SessionLocal() as session:
        for adapter in adapters.values():
            try: await run_import(session, adapter)
            except Exception: pass


async def main():
    if not get_settings().parser_scheduler_enabled:
        while True: await asyncio.sleep(3600)
    scheduler = AsyncIOScheduler(timezone="Asia/Tomsk")
    scheduler.add_job(import_all, "cron", hour=3, id="daily-import", max_instances=1)
    scheduler.start()
    await asyncio.Event().wait()


if __name__ == "__main__": asyncio.run(main())

