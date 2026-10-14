"""Academic class/roster authority; no account, role or academic-data backfill.
Revision ID: f25c930d8e22; Revises: f14b820c7d11.
"""
from alembic import op
from src.db.academic_classes import ACADEMIC_TABLES
revision='f25c930d8e22'
down_revision='f14b820c7d11'
branch_labels=None
depends_on=None

def upgrade():
    # Same SQLModel metadata on bootstrap and migration; FK/check/index parity.
    for table in ACADEMIC_TABLES:table.create(op.get_bind(),checkfirst=True)
    op.execute("""CREATE OR REPLACE FUNCTION lh_academic_event_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'Academic class events are append-only'; END; $$""")
    op.execute('DROP TRIGGER IF EXISTS lh_academic_event_immutable ON academicclassevent')
    op.execute('CREATE TRIGGER lh_academic_event_immutable BEFORE UPDATE OR DELETE ON academicclassevent FOR EACH ROW EXECUTE FUNCTION lh_academic_event_immutable()')

def downgrade():raise RuntimeError('Class, roster and identity history must be retained; disable access instead')
