"""initial schema

Revision ID: 0001
"""
from alembic import op
from app import models  # noqa: F401
from app.db import Base

revision = "0001"; down_revision = None; branch_labels = None; depends_on = None


def upgrade():
    Base.metadata.create_all(bind=op.get_bind())
    categories = ["культура", "кино", "театр", "концерты", "it-и-хакатоны", "спорт", "плавание", "образование", "творчество", "волонтёрство", "другое"]
    table = Base.metadata.tables["categories"]
    op.bulk_insert(table, [{"slug": slug, "name": slug.replace("-", " ").capitalize()} for slug in categories])


def downgrade(): Base.metadata.drop_all(bind=op.get_bind())

