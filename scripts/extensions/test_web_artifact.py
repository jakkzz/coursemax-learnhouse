"""Small contracts for the approved off-host frontend build, not runtime acceptance."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = '.github/workflows/route66-web-artifact.yaml'


class WebArtifactTests(unittest.TestCase):
    def test_exact_discovery_exception(self):
        policy = json.loads((ROOT/'docs/extensions/boundary.json').read_text())
        self.assertEqual(policy['exceptions'][WORKFLOW]['sha256'],
                         hashlib.sha256((ROOT/WORKFLOW).read_bytes()).hexdigest())
        self.assertNotIn('.github/', policy['owned_prefixes'])
        self.assertNotIn('.github/workflows/', policy['owned_prefixes'])

    def test_off_host_scope_and_bounded_build(self):
        workflow = (ROOT/WORKFLOW).read_text()
        for required in ('branches: [coursemax/staging]', "github.repository == 'jakkzz/coursemax-learnhouse'",
                         'runs-on: ubuntu-24.04', 'contents: read', 'memory=4g', 'memory-swap=4g',
                         'cpu-quota=200000', 'max-parallelism = 1', '--builder vps-limited',
                         '--target web-artifact', 'SOURCE_REVISION=$GITHUB_SHA',
                         'Dockerfile.upstream-143', 'web-artifact.sha256', 'if-no-files-found: error'):
            self.assertIn(required, workflow)
        for excluded in ('self-hosted', 'secrets.', 'packages: write', 'docker push', 'continue-on-error: true'):
            self.assertNotIn(excluded, workflow)

    def test_artifact_requires_bundle_and_types(self):
        recipe = (ROOT/'deploy/staging/Dockerfile.upstream-143').read_text()
        bundle = recipe.index('RUN bun run build')
        types = recipe.index('node node_modules/typescript/bin/tsc --noEmit')
        export = recipe.index('FROM scratch AS web-artifact')
        self.assertLess(bundle, types)
        self.assertLess(types, export)
        workflow = (ROOT/WORKFLOW).read_text()
        self.assertIn('set -euo pipefail', workflow)
        self.assertIn('standalone/.next/BUILD_ID', workflow)
        self.assertIn('tar -czf web-artifact.tar.gz', workflow)
        self.assertIn('sha256sum web-artifact.tar.gz', workflow)


if __name__ == '__main__':
    unittest.main()
