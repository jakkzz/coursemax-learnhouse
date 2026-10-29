"""Synthetic facade/discovery contracts for namespace extraction (no live I/O)."""
import ast
import asyncio
import importlib
import inspect
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from src.route66_ext.adapters._exports import export_native


class FacadeTests(unittest.TestCase):
    def module(self):
        module = ModuleType('src.synthetic_extension_adapter')
        return module

    def test_dependency_identity_and_signature_preserved(self):
        module = self.module()
        async def get_db_session():
            yield 'fixture'
        module.get_db_session = get_db_session
        with patch.dict(sys.modules, {module.__name__: module}):
            adapter = export_native(module.__name__, ['get_db_session'])
            self.assertIs(adapter['get_db_session'], get_db_session)
            self.assertEqual(inspect.signature(adapter['get_db_session']), inspect.signature(get_db_session))

    def test_mocked_first_import_does_not_capture_temporary_native_function(self):
        module = self.module()
        module.get_redis_client = Mock(return_value='fixture')
        with patch.dict(sys.modules, {module.__name__: module}):
            operation = export_native(module.__name__, ['get_redis_client'])['get_redis_client']
            self.assertEqual(operation(), 'fixture')
            module.get_redis_client = lambda: None
            self.assertIsNone(operation())

    def test_operation_preserves_native_signature_and_current_policy(self):
        module = self.module()
        def decode_jwt(token: str):
            return token
        module.decode_jwt = decode_jwt
        with patch.dict(sys.modules, {module.__name__: module}):
            operation = export_native(module.__name__, ['decode_jwt'])['decode_jwt']
            self.assertEqual(inspect.signature(operation), inspect.signature(decode_jwt))
            module.decode_jwt = Mock(side_effect=ValueError('synthetic-denial'))
            with self.assertRaises(ValueError):
                operation('fixture')

    def test_async_native_failure_propagates(self):
        module = self.module()
        async def enforce_login_auth_method(*args):
            raise ValueError('fixture-denial')
        module.enforce_login_auth_method = enforce_login_auth_method
        with patch.dict(sys.modules, {module.__name__: module}):
            operation = export_native(module.__name__, ['enforce_login_auth_method'])['enforce_login_auth_method']
            with self.assertRaises(ValueError):
                asyncio.run(operation())

    def test_models_are_same_native_objects(self):
        module = self.module()
        module.User = type('User', (), {})
        with patch.dict(sys.modules, {module.__name__: module}):
            self.assertIs(export_native(module.__name__, ['User'])['User'], module.User)

    def test_own_or_external_module_rejected(self):
        for module in ('os', 'src.route66_ext.services.attendance_policy'):
            with self.assertRaises(ValueError):
                export_native(module, [])


class DiscoveryTests(unittest.TestCase):
    def test_native_model_shims_preserve_identity(self):
        from src.route66_ext.bootstrap import register_models
        modules = register_models()
        tables = set()
        # Modules added after extraction have no legacy native shim to preserve.
        unshimmed = {'src.route66_ext.db.school_calendar'}
        for owned in modules:
            legacy = None if owned.__name__ in unshimmed else importlib.import_module(owned.__name__.replace('src.route66_ext.', 'src.', 1))
            for name, value in vars(owned).items():
                if inspect.isclass(value) and value.__module__ == owned.__name__ and hasattr(value, '__table__'):
                    if legacy is not None:
                        self.assertIs(getattr(legacy, name), value)
                    tables.add(value.__table__.name)
        self.assertEqual(tables, {
            'academicclass', 'academicclassevent', 'academicrosterentry',
            'attendancechallenge', 'attendanceevent', 'attendancescan', 'attendancesession',
            'classschedule', 'courseregistrybinding', 'nrruteacheridentity',
            'provideridentity', 'provideridentityevent', 'providerprofileimport',
            'schoolcalendar', 'schoolcalendarattachment', 'schoolcalendarrevision',
            'schoolcalendarsource', 'schoolgoogleevidence', 'schoolstudent', 'teachingassignment',
        })
        self.assertEqual(register_models(), modules)

    def test_bootstrap_unique_existing_route_paths(self):
        from src.route66_ext.bootstrap import build_router
        from fastapi import FastAPI
        import warnings
        app = FastAPI()
        app.include_router(build_router())
        # Current FastAPI resolves included routers lazily; inspect its public
        # resolved OpenAPI contract rather than private _IncludedRouter fields.
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            schema = app.openapi()
        self.assertFalse([w for w in captured if 'Duplicate Operation ID' in str(w.message)])
        identifiers = [operation['operationId'] for path in schema['paths'].values()
                       for operation in path.values() if isinstance(operation, dict) and 'operationId' in operation]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        for path in ('/auth/google/start', '/auth/line/start', '/school-identity/me', '/academic-classes', '/attendance/check-in', '/school-calendars', '/school-calendars/schedules/apply'):
            self.assertIn(path, schema['paths'])

    def test_migration_wrappers_preserve_revision_graph(self):
        root = Path(__file__).resolve().parents[4]
        expected = ['c71a02d9ef40', 'd84e13a6b902', 'e92d7f04ab16', 'f14b820c7d11', 'f25c930d8e22', 'f36da41e9f33']
        previous = 'b6e199d023f8'
        for revision in expected:
            path = next((root / 'migrations/versions').glob(revision + '_*.py'))
            spec = importlib.util.spec_from_file_location('fixture_' + revision, path)
            wrapper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(wrapper)
            self.assertEqual(wrapper.revision, revision)
            self.assertEqual(wrapper.down_revision, previous)
            self.assertTrue(wrapper.upgrade.__module__.startswith('src.route66_ext.migrations.'))
            previous = revision

    def test_composed_migrations_have_one_owned_head_without_duplicate_old_implementations(self):
        from alembic.script import ScriptDirectory
        from src.route66_ext.migrations.config import migration_config
        script = ScriptDirectory.from_config(migration_config())
        self.assertEqual(script.get_heads(), ["d5ab36f3c924"])
        self.assertEqual(script.get_revision("d5ab36f3c924").down_revision,
                         ("c4fa25e2b813", "e8f9a0b1c2d3"))
        self.assertEqual(script.get_revision("c4fa25e2b813").down_revision, "b3e9c4d1a702")
        self.assertEqual(script.get_revision("b3e9c4d1a702").down_revision, "f47eb52fa044")
        self.assertEqual(script.get_revision("f47eb52fa044").down_revision, "f36da41e9f33")

    def test_native_imports_confined_to_adapters(self):
        root = Path(__file__).resolve().parents[2]
        for file in root.rglob('*.py'):
            if 'adapters' in file.parts or 'tests' in file.parts:
                continue
            for node in ast.walk(ast.parse(file.read_text())):
                if isinstance(node, ast.ImportFrom) and node.module:
                    self.assertFalse(node.module.startswith('config.'), str(file))
                    if node.module.startswith('src.'):
                        self.assertTrue(node.module.startswith('src.route66_ext.'), (str(file), node.module))


if __name__ == '__main__':
    unittest.main()
