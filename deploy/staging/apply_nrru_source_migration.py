#!/usr/bin/env python3
"""Explicit named migration for bootstrap-created staging schemas (never stamp).

Run only from the verified candidate image after protected backup + isolated
restore. Ordinary Alembic deployments use the composed migration configuration.
No record is inserted/updated/deleted and no native migration head is inferred.
"""
import json
import os

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from src.route66_ext.migrations.versions import f47eb52fa044_course_export_source as migration


def main():
    url = os.environ['LEARNHOUSE_SQL_CONNECTION_STRING'].replace('postgresql+asyncpg://', 'postgresql://', 1)
    if not url.startswith('postgresql://'):
        raise SystemExit('Expected the existing staging PostgreSQL connection')
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(text('SELECT pg_advisory_xact_lock(664466, 1)'))
            before = inspect(connection)
            # This entry point is specifically for the existing unversioned
            # native-bootstrap deployment, not a replacement Alembic history.
            if before.has_table('alembic_version'):
                raise RuntimeError('Versioned database: use the composed Alembic migration graph')
            columns = before.get_columns('academicclass')
            unique = before.get_unique_constraints('academicclass')
            expected = {'id','course_id','academic_year','semester','section','registry_course_id',
                        'registry_class_id','registry_course_code','version','last_source_hash','last_synced_at'}
            if {c['name'] for c in columns} != expected:
                raise RuntimeError('Unexpected class schema; preserve it for review')
            old_unique = {c['name']: tuple(c['column_names']) for c in unique}
            required = {'uq_official_class_term': ('registry_class_id','academic_year','semester'),
                        'uq_course_section_term': ('course_id','academic_year','semester','section')}
            if any(old_unique.get(k) != v for k,v in required.items()):
                raise RuntimeError('Existing class ownership constraints differ')
            new_name = 'uq_official_course_section_term'
            new_columns = ('registry_course_id','academic_year','semester','section')
            if new_name in old_unique and old_unique[new_name] != new_columns:
                raise RuntimeError('New constraint name has an unexpected definition')
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            after = inspect(connection)
            after_columns = after.get_columns('academicclass')
            for a,b in zip(columns, after_columns, strict=True):
                a,b = dict(a),dict(b)
                a['type'], b['type'] = str(a['type']), str(b['type'])
                if a['name'] == 'registry_class_id':
                    if b['nullable'] is not True: raise RuntimeError('Nullability migration failed')
                    a.pop('nullable'); b.pop('nullable')
                if a != b: raise RuntimeError('Unexpected column mutation')
            constraints = {c['name']: tuple(c['column_names']) for c in after.get_unique_constraints('academicclass')}
            if constraints != {**old_unique, new_name:new_columns}:
                raise RuntimeError('Unexpected uniqueness mutation')
        print(json.dumps({'migration':migration.revision,'native_alembic_stamped':False,
                          'academic_rows_written':False,'registry_class_id_nullable':True,
                          'official_tuple_unique':True}))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
