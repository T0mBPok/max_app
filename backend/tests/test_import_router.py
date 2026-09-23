import uuid
from datetime import UTC, datetime

from fastapi import Response, status

from src.classifiers.enums import ImportStatus
from src.imports.models import ImportRun
from src.imports.router import _run_out, _set_batch_status


def make_run(run_status: ImportStatus) -> ImportRun:
    return ImportRun(
        id=uuid.uuid4(),
        source_id=uuid.uuid4(),
        status=run_status,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        received_count=0,
        created_count=0,
        updated_count=0,
        unchanged_count=0,
        skipped_count=0,
        error_count=0,
    )


def test_run_output_contains_human_readable_source():
    result = _run_out(make_run(ImportStatus.SUCCESS), "aquatika", "Акватика")

    assert result.source_code == "aquatika"
    assert result.source_name == "Акватика"


def test_batch_http_status_reports_mixed_and_total_failure():
    success = _run_out(make_run(ImportStatus.SUCCESS), "ok", "OK")
    failed = _run_out(make_run(ImportStatus.FAILED), "failed", "Failed")

    mixed_response = Response()
    _set_batch_status(mixed_response, [success, failed])
    assert mixed_response.status_code == status.HTTP_207_MULTI_STATUS

    failed_response = Response()
    _set_batch_status(failed_response, [failed])
    assert failed_response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
