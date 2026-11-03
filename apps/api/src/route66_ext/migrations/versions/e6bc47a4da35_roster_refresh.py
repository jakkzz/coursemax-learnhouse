"""Fenced roster scheduling and explicitly attributed system history.

Revision ID: e6bc47a4da35
Revises: d5ab36f3c924
"""
from alembic import op
from sqlalchemy import inspect, text
from src.route66_ext.db.academic_classes import SCHEDULED_ACTOR_CHECK
from src.route66_ext.db.roster_refresh import AcademicRosterRefresh

revision = 'e6bc47a4da35'
down_revision = 'd5ab36f3c924'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    columns = {c['name']: c for c in inspect(connection).get_columns('academicclassevent')}
    if not columns['actor_user_id']['nullable']:
        op.alter_column('academicclassevent', 'actor_user_id', nullable=True)
    checks = {c['name'] for c in inspect(connection).get_check_constraints('academicclassevent')}
    if 'ck_academic_event_actor' not in checks:
        op.create_check_constraint('ck_academic_event_actor', 'academicclassevent', SCHEDULED_ACTOR_CHECK)
    AcademicRosterRefresh.__table__.create(connection, checkfirst=True)


def downgrade():
    connection = op.get_bind()
    if connection.execute(text('SELECT EXISTS (SELECT 1 FROM academicclassevent WHERE actor_user_id IS NULL)')).scalar():
        raise RuntimeError('Keep scheduled academic history; use compatible code rollback, not schema downgrade')
    if connection.execute(text('SELECT EXISTS (SELECT 1 FROM academicrosterrefresh)')).scalar():
        raise RuntimeError('Keep refresh state and approval evidence; schema downgrade requires an empty table')
    op.drop_table('academicrosterrefresh')
    op.drop_constraint('ck_academic_event_actor', 'academicclassevent', type_='check')
    op.alter_column('academicclassevent', 'actor_user_id', nullable=False)
