"""Small recovery/packaging contracts; schema behavior is rehearsed on a restore."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('recover', ROOT / 'recover_app_runtime.py')
recover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recover)


class RecoveryTests(unittest.TestCase):
    def fixture(self):
        return {'Image': 'sha256:retained', 'Config': {'Env': ['SECRET=synthetic$literal', 'EMPTY='],
            'Cmd': ['sh', '/app/start.sh'], 'Labels': {'com.docker.compose.project': 'old', 'custom': 'kept'},
            'Healthcheck': {'Test': ['CMD', 'true'], 'Interval': 1000000000, 'Retries': 3}},
            'HostConfig': {'RestartPolicy': {'Name': 'unless-stopped'}, 'LogConfig': {'Type': 'json-file', 'Config': {}},
                'ReadonlyRootfs': False, 'Memory': 1536*1024**2, 'NanoCpus': 1500000000},
            'NetworkSettings': {'Networks': {'existing': {'Aliases': ['app']}}},
            'Mounts': [{'Type': 'volume', 'Name': 'existing-content', 'Destination': '/app/api/content', 'RW': True}]}

    def test_exact_private_recovery_without_secret_generation(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            obj = self.fixture()
            (directory / 'app.inspect.json').write_text(json.dumps(obj))
            result = json.loads(recover.recover(directory).read_text())
            app = result['services']['app']
            self.assertEqual((directory / 'app.env').read_text().splitlines(), obj['Config']['Env'])
            self.assertEqual((directory / 'app.env').stat().st_mode & 0o777, 0o600)
            self.assertEqual(app['image'], obj['Image'])
            self.assertEqual(app['command'], obj['Config']['Cmd'])
            self.assertEqual(app['env_file'][0]['format'], 'raw')
            self.assertEqual(app['labels'], {'custom': 'kept'})
            self.assertTrue(result['volumes']['existing-content']['external'])
            self.assertEqual(app['healthcheck']['interval'], '1000000000ns')
            self.assertEqual(app['cpus'], 1.5)

    def test_multiline_environment_is_not_silently_corrupted(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            obj = self.fixture(); obj['Config']['Env'] = ['SECRET=one\ntwo']
            (directory / 'app.inspect.json').write_text(json.dumps(obj))
            with self.assertRaises(ValueError):
                recover.recover(directory)

    def test_matching_build_not_old_runtime_overlay(self):
        recipe = (ROOT / 'Dockerfile.upstream-143').read_text()
        for required in ('python:3.14.7-alpine3.24', 'node:24.22.1-alpine3.24', 'oven/bun:1.4.4-alpine',
                         'uv sync --frozen', 'bun install --frozen-lockfile', 'bun run test',
                         'node node_modules/typescript/bin/tsc --noEmit', '/app/api/src/route66_ext/start.sh',
                         'COPY --chown=nextjs:nodejs old-static/'):
            self.assertIn(required, recipe)
        self.assertNotIn('FROM coursemax-learnhouse:', recipe)


if __name__ == '__main__':
    unittest.main()
