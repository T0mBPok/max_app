"""hide address records produced by the old PFDO JSON parser

Revision ID: 0002
"""

from alembic import op
from sqlalchemy import text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


ADDRESS_PATTERN = (
    r"(^|[ ,])(ул\.?|улица|проспект|пр-т|переулок|пер\.?|дом|д\.?|шоссе|тракт|"
    r"микрорайон|мкр\.?)([ ,]|$)"
)


def upgrade():
    connection = op.get_bind()
    connection.execute(
        text(
            """
        UPDATE activities
        SET status = 'STALE'
        WHERE id IN (
            SELECT sr.activity_id
            FROM source_records sr
            JOIN sources s ON s.id = sr.source_id
            JOIN activities a ON a.id = sr.activity_id
            WHERE s.code = 'tomsk_pfdo'
              AND lower(a.title) ~ :pattern
        )
        """
        ),
        {"pattern": ADDRESS_PATTERN},
    )
    connection.execute(
        text(
            """
        DELETE FROM source_records
        WHERE id IN (
            SELECT sr.id
            FROM source_records sr
            JOIN sources s ON s.id = sr.source_id
            JOIN activities a ON a.id = sr.activity_id
            WHERE s.code = 'tomsk_pfdo'
              AND lower(a.title) ~ :pattern
        )
        """
        ),
        {"pattern": ADDRESS_PATTERN},
    )


def downgrade():
    # Удалённую связь с ошибочным источником восстановить достоверно невозможно.
    pass
