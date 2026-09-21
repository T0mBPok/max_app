import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.deps import SessionDep
from app.errors import not_found
from app.imports.registry import adapters
from app.imports.service import run_import
from app.models import ImportRun
from app.schemas import ImportRunOut

router = APIRouter(prefix="/admin/imports", tags=["imports"])


@router.post("/{source_code}/run", response_model=ImportRunOut)
async def run_one(source_code: str, session: SessionDep):
    adapter = adapters.get(source_code)
    if not adapter: raise not_found("IMPORT_SOURCE_NOT_FOUND", "Источник не найден")
    return await run_import(session, adapter)


@router.post("/run-all", response_model=list[ImportRunOut])
async def run_all(session: SessionDep): return [await run_import(session, adapter) for adapter in adapters.values()]


@router.get("", response_model=list[ImportRunOut])
async def runs(session: SessionDep): return (await session.scalars(select(ImportRun).order_by(ImportRun.started_at.desc()).limit(100))).all()


@router.get("/{run_id}", response_model=ImportRunOut)
async def run_detail(run_id: uuid.UUID, session: SessionDep):
    run = await session.get(ImportRun, run_id)
    if not run: raise not_found("IMPORT_SOURCE_NOT_FOUND", "Запуск не найден")
    return run
