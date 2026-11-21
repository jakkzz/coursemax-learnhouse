#!/usr/bin/env python3
"""Apply only the two upstream 1.4.3 revisions to an unversioned bootstrap DB.

Rehearse on an isolated restore first. Quiesce the app before live application.
No inferred Alembic stamp, account backfill or historic migration-chain replay.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import BigInteger, create_engine, inspect, text

REVISIONS = ('d7e8f9a0b1c2_add_used_link_token', 'e8f9a0b1c2d3_add_billing_interval_to_paymentsoffer')


def snapshot(connection, tables, billing_added):
    results = {}
    quote = connection.dialect.identifier_preparer.quote
    for table in tables:
        projection = "to_jsonb(t) - 'billing_interval'" if table == 'paymentsoffer' and billing_added else 'to_jsonb(t)'
        digest, count = hashlib.sha256(), 0
        for row in connection.execute(text(f'SELECT ({projection})::text FROM {quote(table)} t ORDER BY ({projection})::text')).scalars():
            digest.update(row.encode()); digest.update(b'\n'); count += 1
        results[table] = [count, digest.hexdigest()]
    return results


def upgrade(connection):
    connection.execute(text('SELECT pg_advisory_xact_lock(664466, 1)'))
    inspector = inspect(connection)
    tables = inspector.get_table_names()
    if 'alembic_version' in tables:
        raise RuntimeError('Versioned database: use the composed Alembic graph instead')
    if not {'user', 'activity', 'provideridentity', 'schoolcalendarrevision'} <= set(tables):
        raise RuntimeError('Not the expected LearnHouse extension bootstrap schema')
    billing_added = ('paymentsoffer' in tables and 'billing_interval' not in
                     {col['name'] for col in inspector.get_columns('paymentsoffer')})
    before = snapshot(connection, tables, billing_added)
    with Operations.context(MigrationContext.configure(connection)):
        for name in REVISIONS:
            path = Path('migrations/versions') / (name + '.py')
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.upgrade()
    if snapshot(connection, tables, billing_added) != before:
        raise RuntimeError('Existing rows changed; transaction rolled back')
    inspector = inspect(connection)
    if set(inspector.get_table_names()) != set(tables) | {'used_link_token'}:
        raise RuntimeError('Unexpected table delta')
    columns = {col['name']: col for col in inspector.get_columns('used_link_token')}
    if set(columns) != {'jti', 'purpose', 'expires_at'} or not isinstance(columns['expires_at']['type'], BigInteger):
        raise RuntimeError('Unexpected spent-token schema')
    if inspector.get_pk_constraint('used_link_token')['constrained_columns'] != ['jti']:
        raise RuntimeError('Spent-token single-use primary key missing')
    return {'revisions': [name.split('_', 1)[0] for name in REVISIONS], 'native_alembic_stamped': False,
            'existing_tables_verified': len(tables), 'existing_rows_preserved': True,
            'added_tables': sorted(set(inspector.get_table_names()) - set(tables)),
            'billing_interval_added': billing_added}


if __name__ == '__main__':
    url = os.environ['LEARNHOUSE_SQL_CONNECTION_STRING'].replace('postgresql+asyncpg://', 'postgresql://', 1)
    if not url.startswith('postgresql://'):
        raise RuntimeError('Expected explicit PostgreSQL URL')
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            result = upgrade(connection)
        print(json.dumps(result))
    finally:
        engine.dispose()
