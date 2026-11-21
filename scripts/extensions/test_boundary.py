import hashlib
import unittest
from check_boundary import violations
from dry_run import Relocate
import ast
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
import check_boundary


class GitGateTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='route66-boundary-test-')
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.git('init', '-q')
        self.native = self.root / 'apps/api/src/security/auth.py'
        self.native.parent.mkdir(parents=True)
        self.native.write_text('# Synthetic native fixture\n')
        self.git('add', '.')
        self.commit()
        self.policy = self.root / 'docs/extensions/boundary.json'
        self.policy.parent.mkdir(parents=True)
        self.policy.write_text(json.dumps({
            'snapshot': self.git('rev-parse', 'HEAD').strip(), 'exceptions': {},
            'owned_files': [], 'owned_prefixes': ['docs/extensions/', 'apps/api/src/route66_ext/'],
            'preserved_untracked_files': ['unrelated.yaml'], 'preserved_untracked_prefixes': ['.impeccable/']}))

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.root).decode()

    def commit(self):
        self.git('-c', 'user.email=fixture@example.invalid', '-c', 'user.name=Fixture',
                 '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture')

    def gate(self):
        with patch.object(check_boundary, 'ROOT', self.root), patch.object(check_boundary, 'POLICY', self.policy), contextlib.redirect_stdout(io.StringIO()):
            return check_boundary.main()

    def test_working_staged_and_committed_native_changes_blocked(self):
        self.native.write_text('# Changed synthetic fixture\n')
        self.assertEqual(self.gate(), 1)
        self.git('add', 'apps/api/src/security/auth.py')
        self.assertEqual(self.gate(), 1)
        self.commit()
        self.assertEqual(self.gate(), 1)

    def test_untracked_native_blocked_but_own_and_preserved_allowed(self):
        own = self.root / 'apps/api/src/route66_ext/policy.py'
        own.parent.mkdir(parents=True)
        own.write_text('# own fixture\n')
        (self.root / 'unrelated.yaml').write_text('# preserved fixture\n')
        self.assertEqual(self.gate(), 0)
        (self.native.parent / 'new_native.py').write_text('# outside boundary\n')
        self.assertEqual(self.gate(), 1)

    def test_pinned_upstream_integration_does_not_allow_later_native_drift(self):
        policy = json.loads(self.policy.read_text())
        policy['upstream_baseline'] = policy['snapshot']
        self.native.write_text('# Exact upstream update\n')
        self.git('add', 'apps/api/src/security/auth.py')
        self.commit()
        policy['accepted_upstream_revision'] = self.git('rev-parse', 'HEAD').strip()
        self.policy.write_text(json.dumps(policy))
        self.assertEqual(self.gate(), 0)
        self.native.write_text('# Unreviewed local edit after upstream\n')
        self.assertEqual(self.gate(), 1)
        self.git('add', 'apps/api/src/security/auth.py')
        self.commit()
        self.assertEqual(self.gate(), 1)

    def test_original_deletion_blocked(self):
        self.native.unlink()
        self.assertEqual(self.gate(), 1)


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.policy = {'owned_files': ['AGENTS.md'], 'owned_prefixes': ['src/route66_ext/'],
                       'preserved_untracked_files': ['unrelated.yaml'],
                       'preserved_untracked_prefixes': ['.impeccable/'], 'exceptions': {}}

    def check(self, changes, content=b'new'):
        return violations(changes, self.policy, lambda path: content)

    def test_owned(self):
        self.assertEqual(self.check([('A', 'src/route66_ext/attendance.py')]), [])

    def test_core_update_delete_and_add_are_denied(self):
        for status in ('M', 'D', 'A', '?'):
            self.assertEqual(self.check([(status, 'src/security/auth.py')]), ['src/security/auth.py'])

    def test_preserved_only_ignores_untracked(self):
        self.assertEqual(self.check([('?', 'unrelated.yaml'), ('?', '.impeccable/file')]), [])
        self.assertEqual(self.check([('A', 'unrelated.yaml')]), ['unrelated.yaml'])

    def test_exact_exception(self):
        self.policy['exceptions']['src/security/auth.py'] = {
            'reason': 'Required invariant', 'approval_reference': 'synthetic-test-only',
            'tests': ['session regression'], 'replacement_plan': 'Delegated hook',
            'sha256': hashlib.sha256(b'new').hexdigest()}
        self.assertEqual(self.check([('M', 'src/security/auth.py')]), [])
        self.assertTrue(self.check([('M', 'src/security/auth.py')], b'different'))
        self.assertTrue(self.check([('D', 'src/security/auth.py')], None))

    def test_hash_alone_is_not_exception(self):
        self.policy['exceptions']['src/security/auth.py'] = {'sha256': hashlib.sha256(b'new').hexdigest()}
        self.assertTrue(self.check([('M', 'src/security/auth.py')]))

    def test_pinned_upstream_bytes_only(self):
        path = 'src/security/auth.py'
        allowed = {path: b'upstream'}
        self.assertEqual(violations([('M', path)], self.policy, lambda _: b'upstream', allowed), [])
        self.assertEqual(violations([('M', path)], self.policy, lambda _: b'edited', allowed), [path])
        self.assertEqual(violations([('D', path)], self.policy, lambda _: None, allowed), [path])
        self.assertEqual(violations([('D', path)], self.policy, lambda _: None, {path: None}), [])
        self.assertEqual(violations([('M', path)], self.policy, lambda _: None, {path: None}), [path])

    def test_upstream_cannot_erase_legacy_customization_or_exception(self):
        path = 'src/security/auth.py'
        for key, value in [('legacy_inventory', [{'path': path}]), ('exceptions', {path: {}})]:
            policy = {**self.policy, key: value}
            self.assertEqual(violations([('M', path)], policy, lambda _: b'upstream',
                                        {path: b'upstream'}), [path])

    def test_owned_similar_prefix_is_denied(self):
        self.assertTrue(self.check([('A', 'src/route66_ext_bad/auth.py')]))


class RehearsalTests(unittest.TestCase):
    def rewrite(self, source):
        mapping = {'src.services.attendance_policy': 'src.route66_ext.services.attendance_policy'}
        return ast.unparse(ast.fix_missing_locations(Relocate(mapping).visit(ast.parse(source))))

    def test_direct_import_and_mock_reference(self):
        result = self.rewrite("from src.services.attendance_policy import decide_checkin\npatch('src.services.attendance_policy.decide_checkin')")
        self.assertIn('from src.route66_ext.services.attendance_policy', result)
        self.assertIn("'src.route66_ext.services.attendance_policy.decide_checkin'", result)

    def test_module_from_parent(self):
        self.assertIn('from src.route66_ext.services import attendance_policy as policy',
                      self.rewrite('from src.services import attendance_policy as policy'))

    def test_native_import_kept(self):
        self.assertEqual(self.rewrite('from src.db.users import User'), 'from src.db.users import User')

    def test_unsafe_unaliased_import_refused(self):
        with self.assertRaises(ValueError):
            self.rewrite('import src.services.attendance_policy')


if __name__ == '__main__':
    unittest.main()
