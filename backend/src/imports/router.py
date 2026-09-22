import uuid

from fastapi import APIRouter
from sqlalchemy import select

from src.exceptions import AppError, not_found
from src.imports.logic import run_import
from src.imports.models import ImportRun, Source
from src.imports.registry import adapters
from src.imports.schemas import ImportRunOut
from src.user.dependencies import CurrentUser, SessionDep

router = APIRouter(prefix="/admin/imports", tags=["imports"])


@router.post("/{source_code}/run", response_model=ImportRunOut)
async def run_one(source_code: str, _user: CurrentUser, session: SessionDep):
    adapter = adapters.get(source_code)
    if not adapter:
        raise not_found("IMPORT_SOURCE_NOT_FOUND", "Источник не найден")
    return await run_import(session, adapter)


@router.post("/run-all", response_model=list[ImportRunOut])
async def run_all(_user: CurrentUser, session: SessionDep):
    results = []
    for adapter in adapters.values():
        try:
            results.append(await run_import(session, adapter))
        except AppError:
            source = await session.scalar(select(Source).where(Source.code == adapter.source_code))
            if source:
                failed_run = await session.scalar(
                    select(ImportRun)
                    .where(ImportRun.source_id == source.id)
                    .order_by(ImportRun.started_at.desc())
                    .limit(1)
                )
                if failed_run:
                    results.append(failed_run)
    return results


@router.get("", response_model=list[ImportRunOut])
async def runs(_user: CurrentUser, session: SessionDep):
    return (
        await session.scalars(select(ImportRun).order_by(ImportRun.started_at.desc()).limit(100))
    ).all()


@router.get("/{run_id}", response_model=ImportRunOut)
async def run_detail(run_id: uuid.UUID, _user: CurrentUser, session: SessionDep):
    run = await session.get(ImportRun, run_id)
    if not run:
        raise not_found("IMPORT_SOURCE_NOT_FOUND", "Запуск не найден")
    return run
