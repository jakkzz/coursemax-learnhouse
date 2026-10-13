import importlib.util
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('web_overlay', Path(__file__).with_name('create_web_overlay.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class WebOverlayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.parent = self.root / 'parent'
        self.desired = self.root / 'desired'
        for tree in (self.parent, self.desired):
            for name in ('server.js', '.next/BUILD_ID', '.next/server/app-paths-manifest.json'):
                path = tree / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('same')
        self.output = self.root / 'delta.tar.gz'

    def test_complete_overlay_matches_validated_tree_and_preserves_old_assets(self):
        (self.parent / 'old.js').write_text('in-flight asset')
        (self.desired / 'server.js').write_text('new')
        (self.desired / 'new.js').write_text('new asset')
        (self.desired / 'alias.js').symlink_to('new.js')
        result = module.create(self.parent, self.desired, self.output)
        self.assertEqual(result['required_entries'], 5)
        merged = self.root / 'merged'
        shutil.copytree(self.parent, merged, symlinks=True)
        with tarfile.open(self.output) as archive:
            # This archive was generated above from our own fixture, never user input.
            archive.extractall(merged, filter='fully_trusted')
        for path in self.desired.rglob('*'):
            self.assertEqual(module.signature(path), module.signature(merged / path.relative_to(self.desired)))
        self.assertEqual((merged / 'old.js').read_text(), 'in-flight asset')

    def test_directory_symlink_conflict_fails_before_archive(self):
        (self.parent / 'nested').mkdir()
        (self.desired / 'nested').symlink_to('.next', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'type conflict'):
            module.create(self.parent, self.desired, self.output)
        self.assertFalse(self.output.exists())

    def test_incomplete_input_and_existing_output_refused(self):
        (self.desired / 'server.js').unlink()
        with self.assertRaises(ValueError):
            module.create(self.parent, self.desired, self.output)
        self.output.write_bytes(b'retained')
        with self.assertRaises(ValueError):
            module.create(self.parent, self.parent, self.output)
        self.assertEqual(self.output.read_bytes(), b'retained')


if __name__ == '__main__':
    unittest.main()
