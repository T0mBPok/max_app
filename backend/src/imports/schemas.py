import uuid
from datetime import datetime

from src.classifiers.enums import ImportStatus
from src.common.schemas import ORMModel


class ImportRunOut(ORMModel):
    id: uuid.UUID
    source_id: uuid.UUID
    status: ImportStatus
    started_at: datetime
    finished_at: datetime | None
    received_count: int
    created_count: int
    updated_count: int
    unchanged_count: int
    skipped_count: int
    error_count: int
    error_message: str | None
