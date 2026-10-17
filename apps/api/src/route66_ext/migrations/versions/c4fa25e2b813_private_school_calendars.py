"""Teacher-private calendars, acquisition provenance and frozen proposal attachments.

Existing calendars keep their IDs and become organization-scoped. No academic
rows, source bytes, revision payloads or class-schedule pins are rewritten.
"""
from alembic import op
import sqlalchemy as sa
from src.route66_ext.db.school_calendar import GUARDS, SchoolCalendarAttachment

revision = 'c4fa25e2b813'
down_revision = 'b3e9c4d1a702'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {c['name'] for c in inspector.get_columns('schoolcalendar')}
    if 'scope' not in columns:
        op.add_column('schoolcalendar', sa.Column('scope', sa.String(20), nullable=False, server_default='organization'))
        op.add_column('schoolcalendar', sa.Column('owner_user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=True))
        op.create_index('ix_schoolcalendar_owner_user_id', 'schoolcalendar', ['owner_user_id'])
        op.create_check_constraint('ck_school_calendar_scope', 'schoolcalendar',
            "(scope = 'organization' AND owner_user_id IS NULL) OR (scope = 'teacher' AND owner_user_id IS NOT NULL)")
    if 'uq_school_calendar_track' in {c['name'] for c in inspector.get_unique_constraints('schoolcalendar')}:
        op.drop_constraint('uq_school_calendar_track', 'schoolcalendar', type_='unique')
    if 'uq_school_calendar_shared_track' not in {i['name'] for i in inspector.get_indexes('schoolcalendar')}:
        op.create_index('uq_school_calendar_shared_track', 'schoolcalendar', ['org_id', 'academic_year', 'track'],
                        unique=True, postgresql_where=sa.text("scope = 'organization'"))
    revision_columns = {c['name'] for c in inspector.get_columns('schoolcalendarrevision')}
    for name, kind in [('source_url', sa.String(2048)), ('resolved_url', sa.String(2048)),
                       ('fetched_at', sa.DateTime(timezone=True))]:
        if name not in revision_columns:
            op.add_column('schoolcalendarrevision', sa.Column(name, kind, nullable=True))
    if 'derived_from_revision_id' not in revision_columns:
        op.add_column('schoolcalendarrevision', sa.Column('derived_from_revision_id', sa.Integer(),
                      sa.ForeignKey('schoolcalendarrevision.id'), nullable=True))
    SchoolCalendarAttachment.__table__.create(connection, checkfirst=True)
    for statements in GUARDS.values():
        for statement in statements:
            if statement.startswith('CREATE TRIGGER '):
                name, table = statement.split()[2], statement.split(' ON ')[1].split()[0]
                op.execute(f'DROP TRIGGER IF EXISTS {name} ON {table}')
            op.execute(statement)


def downgrade():
    raise RuntimeError('Private sources, calendar ownership and proposal evidence must be retained; use compatible code recovery')
