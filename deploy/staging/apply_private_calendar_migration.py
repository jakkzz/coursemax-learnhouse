#!/usr/bin/env python3
"""Named forward migration for unversioned staging; no native Alembic stamp.

Use a verified candidate and protected backup/isolated restore before shared-host
application. Dry-run on an isolated restored database, never against live data.
"""
import hashlib
import json
import os
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from src.route66_ext.adapters.db_organizations import Organization as _Organization
from src.route66_ext.adapters.db_users import User as _User
from src.route66_ext.db.academic_classes import AcademicClassEvent as _Event
from src.route66_ext.migrations.versions import c4fa25e2b813_private_school_calendars as migration

_PROTECTED = ('academicclass', 'academicclassevent', 'academicrosterentry', 'schoolstudent',
              'attendancesession', 'attendancechallenge', 'attendancescan', 'attendanceevent',
              'classschedule', 'schoolcalendarsource', 'schoolcalendar', 'schoolcalendarrevision',
              'user', 'provideridentity', 'schoolgoogleevidence', 'nrruteacheridentity',
              'course', 'teachingassignment', 'courseregistrybinding', 'trailstep', 'trailrun')
_ADDED = {'schoolcalendar': ('scope', 'owner_user_id'), 'schoolcalendarrevision':
          ('source_url', 'resolved_url', 'fetched_at', 'derived_from_revision_id')}


def snapshot(connection):
    result = {}
    inspector = inspect(connection)
    for table in _PROTECTED:
        if not inspector.has_table(table):
            continue
        projection = 'to_jsonb(t)' + ''.join(" - '" + column + "'" for column in _ADDED.get(table, ()))
        rows = connection.execute(text(f'SELECT ({projection})::text FROM "{table}" t ORDER BY ({projection})::text')).scalars()
        digest, count = hashlib.sha256(), 0
        for row in rows:
            digest.update(row.encode()); digest.update(b'\n'); count += 1
        result[table] = (count, digest.hexdigest())
    return result


def main():
    url = os.environ['LEARNHOUSE_SQL_CONNECTION_STRING'].replace('postgresql+asyncpg://', 'postgresql://', 1)
    if not url.startswith('postgresql://'):
        raise RuntimeError('Expected PostgreSQL')
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock(664466, 1)'))
            inspector = inspect(connection)
            if inspector.has_table('alembic_version'):
                raise RuntimeError('Versioned database: use the composed Alembic migration graph')
            if not all(inspector.has_table(t) for t in ('schoolcalendar', 'schoolcalendarrevision', 'classschedule')):
                raise RuntimeError('Apply the shared school-calendar migration first')
            before = snapshot(connection)
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            if snapshot(connection) != before:
                raise RuntimeError('Existing academic or identity evidence changed; transaction rolled back')
        print(json.dumps({'migration': migration.revision, 'native_alembic_stamped': False,
                          'protected_tables_unchanged': list(before), 'existing_rows_preserved': True}))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
