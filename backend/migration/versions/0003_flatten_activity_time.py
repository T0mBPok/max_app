"""store date and time directly on an activity

Revision ID: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    activity_columns = {column["name"] for column in inspector.get_columns("activities")}

    if "starts_at" not in activity_columns:
        op.add_column("activities", sa.Column("starts_at", sa.DateTime(timezone=True)))
        op.create_index("ix_activities_starts_at", "activities", ["starts_at"])
    if "ends_at" not in activity_columns:
        op.add_column("activities", sa.Column("ends_at", sa.DateTime(timezone=True)))

    if "activity_occurrences" in tables:
        connection.execute(
            sa.text(
                """
                UPDATE activities AS activity
                SET starts_at = occurrence.starts_at,
                    ends_at = occurrence.ends_at
                FROM (
                    SELECT DISTINCT ON (activity_id)
                        activity_id, starts_at, ends_at
                    FROM activity_occurrences
                    ORDER BY activity_id, starts_at
                ) AS occurrence
                WHERE activity.id = occurrence.activity_id
                  AND activity.starts_at IS NULL
                """
            )
        )

    room_columns = {column["name"] for column in inspector.get_columns("rooms")}
    if "meeting_at" in room_columns:
        connection.execute(
            sa.text(
                """
                UPDATE activities AS activity
                SET starts_at = COALESCE(activity.starts_at, room.meeting_at),
                    address = COALESCE(activity.address, room.meeting_point)
                FROM (
                    SELECT activity_id,
                           min(meeting_at) AS meeting_at,
                           min(meeting_point) AS meeting_point
                    FROM rooms
                    GROUP BY activity_id
                ) AS room
                WHERE activity.id = room.activity_id
                """
            )
        )
    if "occurrence_id" in room_columns:
        for foreign_key in inspector.get_foreign_keys("rooms"):
            if foreign_key["constrained_columns"] == ["occurrence_id"]:
                op.drop_constraint(foreign_key["name"], "rooms", type_="foreignkey")
                break
        op.drop_column("rooms", "occurrence_id")

    if "meeting_at" in room_columns:
        op.drop_column("rooms", "meeting_at")
    if "meeting_point" in room_columns:
        op.drop_column("rooms", "meeting_point")

    if "activity_occurrences" in tables:
        op.drop_table("activity_occurrences")


def downgrade():
    connection = op.get_bind()
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())

    if "activity_occurrences" not in tables:
        op.create_table(
            "activity_occurrences",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("activity_id", sa.Uuid(), nullable=False),
            sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ends_at", sa.DateTime(timezone=True)),
            sa.Column("registration_deadline", sa.DateTime(timezone=True)),
            sa.Column("capacity", sa.Integer()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        )
        op.create_index(
            "ix_activity_occurrences_activity_id",
            "activity_occurrences",
            ["activity_id"],
        )
        op.create_index(
            "ix_activity_occurrences_starts_at",
            "activity_occurrences",
            ["starts_at"],
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO activity_occurrences (
                    id, activity_id, starts_at, ends_at, created_at, updated_at
                )
                SELECT gen_random_uuid(), id, starts_at, ends_at, now(), now()
                FROM activities
                WHERE starts_at IS NOT NULL
                """
            )
        )

    room_columns = {column["name"] for column in inspect(connection).get_columns("rooms")}
    if "meeting_at" not in room_columns:
        op.add_column("rooms", sa.Column("meeting_at", sa.DateTime(timezone=True)))
    if "meeting_point" not in room_columns:
        op.add_column("rooms", sa.Column("meeting_point", sa.String(length=500)))
    if "occurrence_id" not in room_columns:
        op.add_column("rooms", sa.Column("occurrence_id", sa.Uuid()))
        op.create_foreign_key(
            "rooms_occurrence_id_fkey",
            "rooms",
            "activity_occurrences",
            ["occurrence_id"],
            ["id"],
        )

    activity_columns = {column["name"] for column in inspect(connection).get_columns("activities")}
    if "ends_at" in activity_columns:
        op.drop_column("activities", "ends_at")
    if "starts_at" in activity_columns:
        op.drop_index("ix_activities_starts_at", table_name="activities")
        op.drop_column("activities", "starts_at")
