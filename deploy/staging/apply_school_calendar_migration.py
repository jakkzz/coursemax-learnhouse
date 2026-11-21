#!/usr/bin/env python3
"""Explicit named school-calendar migration for bootstrap-created staging schemas (never stamp).

Run only from the verified candidate image after protected backup + isolated
restore, before starting the new app. Ordinary Alembic deployments use the
composed migration configuration. The only row write is the deterministic
academicclass.org_id backfill from each class's existing course; class,
roster, session and receipt IDs are unchanged and no native head is inferred.
"""
import json
import os

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

# This is a standalone runner, not app startup: register the native FK targets
# through existing typed adapters before creating the owned calendar tables.
from src.route66_ext.adapters.db_organizations import Organization as _NativeOrganization
from src.route66_ext.adapters.db_users import User as _NativeUser
from src.route66_ext.migrations.versions import b3e9c4d1a702_school_calendar as migration

_CLASS_BEFORE = {'id', 'course_id', 'academic_year', 'semester', 'section', 'registry_course_id',
                 'registry_class_id', 'registry_course_code', 'version', 'last_source_hash', 'last_synced_at'}
_SESSION_BEFORE = {'id', 'class_id', 'title', 'starts_at', 'ends_at', 'timezone', 'grace_minutes',
                   'late_threshold_minutes', 'state', 'version', 'created_by'}
_COUNTED = ('academicclass', 'academicrosterentry', 'attendancesession', 'attendancechallenge',
            'attendancescan', 'attendanceevent', 'academicclassevent')


def _counts(connection):
    return {t: connection.execute(text(f'SELECT count(*) FROM {t}')).scalar_one() for t in _COUNTED}


def main():
    url = os.environ['LEARNHOUSE_SQL_CONNECTION_STRING'].replace('postgresql+asyncpg://', 'postgresql://', 1)
    if not url.startswith('postgresql://'):
        raise SystemExit('Expected the existing staging PostgreSQL connection')
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock(664466, 1)'))
            before = inspect(connection)
            if before.has_table('alembic_version'):
                raise RuntimeError('Versioned database: use the composed Alembic migration graph')
            class_columns = {c['name'] for c in before.get_columns('academicclass')}
            session_columns = {c['name'] for c in before.get_columns('attendancesession')}
            if class_columns != _CLASS_BEFORE or session_columns != _SESSION_BEFORE:
                raise RuntimeError('Unexpected class or attendance schema; preserve it for review')
            if not {c['name'] for c in before.get_unique_constraints('academicclass')} >= {'uq_official_course_section_term'}:
                raise RuntimeError('Apply the NRRU course-export migration first')
            for table in ('schoolcalendar', 'schoolcalendarsource', 'schoolcalendarrevision', 'classschedule'):
                if before.has_table(table) and connection.execute(text(f'SELECT 1 FROM {table} LIMIT 1')).first():
                    raise RuntimeError(f'{table} already holds data; preserve it for review')
            counts = _counts(connection)
            ids = connection.execute(text('SELECT id, course_id FROM academicclass ORDER BY id')).all()
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            if _counts(connection) != counts:
                raise RuntimeError('Unexpected row count change')
            after = connection.execute(text('SELECT id, course_id FROM academicclass ORDER BY id')).all()
            unscoped = connection.execute(text('''SELECT count(*) FROM academicclass c JOIN course k ON k.id=c.course_id
                                                   WHERE c.org_id IS DISTINCT FROM k.org_id''')).scalar_one()
            if after != ids or unscoped:
                raise RuntimeError('Class identity or organization backfill mismatch')
        print(json.dumps({'migration': migration.revision, 'native_alembic_stamped': False,
                          'class_org_backfilled': len(ids), 'rows_inserted_or_deleted': False,
                          'attendance_guard_extended': True, 'calendar_tables': True}))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
