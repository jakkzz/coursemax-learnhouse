"""Opt-in compatibility for upstream's SQLite-only native unit tests.

Run pytest -p src.route66_ext.tests.sqlite_native_tests. PostgreSQL regex CHECKs
cannot compile on SQLite when the extension router registers its models. Omit
only those CHECKs in this test process; actual extension invariants are tested
separately on PostgreSQL. Never import this plugin in the application.
"""
from sqlalchemy import CheckConstraint


def pytest_collection_modifyitems():
    from src.route66_ext.bootstrap import register_models
    tables = {value.__table__ for module in register_models()
              for value in vars(module).values()
              if getattr(value, '__module__', None) == module.__name__ and hasattr(value, '__table__')}
    for table in tables:
        for constraint in table.constraints:
            if isinstance(constraint, CheckConstraint) and '~' in str(constraint.sqltext):
                constraint.ddl_if(dialect='postgresql')
