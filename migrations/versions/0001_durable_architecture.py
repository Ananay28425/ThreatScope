"""Create v2 tables and retain legacy source tables unchanged.
Revision ID: 0001
"""
import json

from alembic import op
from sqlalchemy import MetaData, Table, inspect, select

from backend.app.tables import Base, LegacyArchive

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    old_tables = set(inspect(bind).get_table_names())
    Base.metadata.create_all(bind)
    for name in ("signals", "alerts"):
        if name not in old_tables:
            continue
        table = Table(name, MetaData(), autoload_with=bind)
        for row in bind.execute(select(table)).mappings():
            # Historical records cannot enter the verified v2 correlation/evaluation path.
            payload = json.loads(json.dumps(dict(row), default=str))
            bind.execute(LegacyArchive.__table__.insert().values(
                table_name=name, row_id=str(row["id"]), body=payload, research_eligible=False,
            ))


def downgrade():
    raise RuntimeError("Use the documented backup restore procedure; automatic data deletion is disabled.")
