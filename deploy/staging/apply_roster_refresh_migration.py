#!/usr/bin/env python3
"""Named migration for unversioned bootstrap staging; never infer/stamp a head.

Run from the verified candidate after the protected backup/restore check. It adds
operational storage and permits attributed system events; it rewrites no history.
"""
import json
import os
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from src.route66_ext.migrations.versions import e6bc47a4da35_roster_refresh as migration
from src.route66_ext.db.roster_refresh import AcademicRosterRefresh


def main():
    url = os.environ['LEARNHOUSE_SQL_CONNECTION_STRING'].replace('postgresql+asyncpg://', 'postgresql://', 1)
    if not url.startswith('postgresql://'):
        raise RuntimeError('Expected the existing staging PostgreSQL connection')
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock(664466, 1)'))
            before = inspect(connection)
            if before.has_table('alembic_version'):
                raise RuntimeError('Versioned database: use the composed Alembic migration graph')
            expected = {'id', 'class_id', 'student_id', 'actor_user_id', 'kind', 'details', 'created_at'}
            if {c['name'] for c in before.get_columns('academicclassevent')} != expected:
                raise RuntimeError('Unexpected event schema; preserve it for review')
            foreign = before.get_foreign_keys('academicclassevent')
            if not any(f['constrained_columns'] == ['actor_user_id'] and f['referred_table'] == 'user' and f['referred_columns'] == ['id'] for f in foreign):
                raise RuntimeError('The existing human actor relationship differs')
            trigger = connection.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid='academicclassevent'::regclass AND tgname='lh_academic_event_immutable'")).scalar()
            if trigger != 'O':
                raise RuntimeError('Existing append-only guard is missing or disabled')
            # Hash immutable rows privately in SQL; output only counts/verification.
            query = "SELECT count(*), md5(COALESCE(string_agg(row_to_json(e)::text, '' ORDER BY id), '')) FROM academicclassevent e"
            evidence = tuple(connection.execute(text(query)).one())
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            after = inspect(connection)
            if {c['name'] for c in after.get_columns('academicrosterrefresh')} != set(AcademicRosterRefresh.__table__.columns.keys()):
                raise RuntimeError('Unexpected refresh state schema')
            if not next(c for c in after.get_columns('academicclassevent') if c['name'] == 'actor_user_id')['nullable']:
                raise RuntimeError('System attribution migration failed')
            if not any(c['name'] == 'ck_academic_event_actor' for c in after.get_check_constraints('academicclassevent')):
                raise RuntimeError('System attribution constraint is missing')
            if tuple(connection.execute(text(query)).one()) != evidence:
                raise RuntimeError('Event history changed during migration')
        print(json.dumps({'migration': migration.revision, 'native_alembic_stamped': False,
                          'event_history_unchanged': True, 'historical_event_count': evidence[0]}))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
