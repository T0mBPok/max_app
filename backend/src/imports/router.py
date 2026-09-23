import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from src.classifiers.enums import ImportStatus
from src.exceptions import AppError, not_found
from src.imports.logic import run_import
from src.imports.models import ImportRun, Source
from src.imports.registry import VOLUNTEERING_SOURCE_CODES, adapters
from src.imports.schemas import ImportRunOut, ImportSourceOut
from src.user.dependencies import SessionDep

router = APIRouter(prefix="/admin/imports", tags=["imports"])


def _run_out(run: ImportRun, source_code: str, source_name: str) -> ImportRunOut:
    return ImportRunOut.model_validate(run).model_copy(
        update={"source_code": source_code, "source_name": source_name}
    )


def _set_batch_status(response: Response, results: list[ImportRunOut]) -> None:
    failed = sum(result.status == ImportStatus.FAILED for result in results)
    if not results or failed == len(results):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif failed or any(result.status == ImportStatus.PARTIAL_SUCCESS for result in results):
        response.status_code = status.HTTP_207_MULTI_STATUS


async def _run(source_code: str, session: SessionDep):
    adapter = adapters.get(source_code)
    if not adapter:
        raise not_found("IMPORT_SOURCE_NOT_FOUND", "Источник не найден")
    run = await run_import(session, adapter)
    return _run_out(run, adapter.source_code, adapter.name)


async def _run_many(source_codes: tuple[str, ...], session: SessionDep):
    results = []
    for source_code in source_codes:
        try:
            results.append(await _run(source_code, session))
        except AppError:
            source = await session.scalar(select(Source).where(Source.code == source_code))
            if source:
                failed_run = await session.scalar(
                    select(ImportRun)
                    .where(ImportRun.source_id == source.id)
                    .order_by(ImportRun.started_at.desc())
                    .limit(1)
                )
                if failed_run:
                    adapter = adapters[source_code]
                    results.append(_run_out(failed_run, adapter.source_code, adapter.name))
    return results


@router.get("/sources", response_model=list[ImportSourceOut])
async def sources(session: SessionDep):
    """Доступные загрузчики и результат последнего запуска каждого из них."""
    result = []
    for adapter in adapters.values():
        source = await session.scalar(select(Source).where(Source.code == adapter.source_code))
        last_run = None
        if source:
            last_run = await session.scalar(
                select(ImportRun)
                .where(ImportRun.source_id == source.id)
                .order_by(ImportRun.started_at.desc())
                .limit(1)
            )
        result.append(
            {
                "code": adapter.source_code,
                "name": adapter.name,
                "base_url": adapter.base_url,
                "enabled": source.enabled if source else True,
                "last_successful_run_at": source.last_successful_run_at if source else None,
                "last_run": (
                    _run_out(last_run, adapter.source_code, adapter.name) if last_run else None
                ),
            }
        )
    return result


@router.post("/events/run", response_model=ImportRunOut)
async def run_events(session: SessionDep):
    """Загрузить события из афиши Томской филармонии."""
    return await _run("tomsk_philharmonic", session)


@router.post("/courses/run", response_model=ImportRunOut)
async def run_courses(session: SessionDep):
    """Загрузить курсы из навигатора дополнительного образования."""
    return await _run("tomsk_pfdo", session)


@router.post("/sections/run", response_model=ImportRunOut)
async def run_sections(session: SessionDep):
    """Загрузить секции СК «Акватика»."""
    return await _run("aquatika", session)


@router.post("/volunteering/run", response_model=list[ImportRunOut])
async def run_volunteering(response: Response, session: SessionDep):
    """Загрузить конкретные волонтёрские мероприятия Томска."""
    results = await _run_many(VOLUNTEERING_SOURCE_CODES, session)
    _set_batch_status(response, results)
    return results


@router.post("/{source_code}/run", response_model=ImportRunOut)
async def run_one(source_code: str, session: SessionDep):
    return await _run(source_code, session)


@router.post("/run-all", response_model=list[ImportRunOut])
async def run_all(response: Response, session: SessionDep):
    results = await _run_many(tuple(adapters), session)
    _set_batch_status(response, results)
    return results


@router.get("", response_model=list[ImportRunOut])
async def runs(session: SessionDep):
    values = (
        await session.scalars(select(ImportRun).order_by(ImportRun.started_at.desc()).limit(100))
    ).all()
    source_ids = {run.source_id for run in values}
    sources_by_id = {
        source.id: source
        for source in (await session.scalars(select(Source).where(Source.id.in_(source_ids)))).all()
    }
    return [
        _run_out(run, sources_by_id[run.source_id].code, sources_by_id[run.source_id].name)
        for run in values
    ]


@router.get("/{run_id}", response_model=ImportRunOut)
async def run_detail(run_id: uuid.UUID, session: SessionDep):
    run = await session.get(ImportRun, run_id)
    if not run:
        raise not_found("IMPORT_SOURCE_NOT_FOUND", "Запуск не найден")
    source = await session.get(Source, run.source_id)
    return _run_out(run, source.code, source.name)
