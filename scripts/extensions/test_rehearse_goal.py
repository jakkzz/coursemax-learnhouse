import copy
import pathlib
import subprocess
import sys
import tempfile
import unittest

try:
    from .rehearse_goal import AUDIT_CAPABILITIES, PHASE_MANIFEST, REQUIRED_FILES, audit, validate_manifest
except ImportError:
    from rehearse_goal import AUDIT_CAPABILITIES, PHASE_MANIFEST, REQUIRED_FILES, audit, validate_manifest


class RehearseTests(unittest.TestCase):
    def tree(self, files):
        directory = tempfile.TemporaryDirectory()
        root = pathlib.Path(directory.name)
        for path, content in files.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(content)
        self.addCleanup(directory.cleanup)
        return root

    def base(self):
        files = {path: "export {}\n" for path in REQUIRED_FILES}
        files[REQUIRED_FILES[0]] = "import { redirect } from 'next/navigation'\nexport default function Old(){redirect('/classes')}\n"
        files[REQUIRED_FILES[1]] = "import { redirect } from 'next/navigation'\nexport default function Page(){redirect('/classes')}\n"
        files[REQUIRED_FILES[2]] = "export { default } from '@/extensions/route66/app/orgs/[orgslug]/dash/classes-preview/page'\n"
        files[REQUIRED_FILES[3]] = "const endpoint='/api/v1/academic-classes'; <TeacherTimetable/>; nativeCoursePath('course_x')\n"
        files[REQUIRED_FILES[4]] = "const endpoint='/api/v1/school-identity/me'; function TeacherTimetable(){return <SchoolTimetable/>}\n"
        files[REQUIRED_FILES[5]] = "fetch('/api/v1/school-identity/me'); fetch('/api/v1/school-identity/search'); fetch('/api/v1/school-identity/confirm'); const confirm_own_name=true\n"
        files[REQUIRED_FILES[6]] = "router.include_router(school_identity.router); router.include_router(academic_classes.router); router.include_router(class_attendance.router)\n"
        files[REQUIRED_FILES[7]] = "router.include_router(class_connections_router); router.include_router(learning_access_router)\n"
        files[REQUIRED_FILES[8]] = "router = APIRouter(prefix='/connections')\n"
        files[REQUIRED_FILES[9]] = "router = APIRouter()\n"
        files[REQUIRED_FILES[10]] = "def can_read(): pass\n"
        files[REQUIRED_FILES[11]] = "class AttendanceSession: pass\n"
        files[REQUIRED_FILES[12]] = "def check_in(): pass\n"
        files[REQUIRED_FILES[13]] = "router = APIRouter()\n"
        files[REQUIRED_FILES[14]] = "export default function Attendance(){}\n"
        files[REQUIRED_FILES[15]] = "export { default } from '@/extensions/route66/app/orgs/[orgslug]/(withmenu)/attendance/page'\n"
        return files

    def test_complete_source_contract_is_observed_but_not_accepted(self):
        result = audit(self.tree(self.base()))
        self.assertTrue(result["ok"])
        self.assertEqual(result["counts"]["audit_ids"], 52)
        self.assertEqual(result["counts"]["pending_audit_decisions"], 52)
        self.assertIn("NOT runtime", result["acceptance"])
        self.assertTrue(all(row["runtime_evidence_required"] for row in result["audit_ledger"]))

    def test_source_mutation_changes_nonconstant_outcome(self):
        good = audit(self.tree(self.base()))
        files = self.base()
        files[REQUIRED_FILES[4]] = "export default function TeacherTimetable(){}\n"
        bad = audit(self.tree(files))
        self.assertTrue(good["ok"])
        self.assertFalse(bad["ok"])
        self.assertIn("teacher_timetable_contract", bad["structural_failures"])

    def test_missing_required_file_fails(self):
        files = self.base()
        del files[REQUIRED_FILES[10]]
        result = audit(self.tree(files))
        self.assertFalse(result["ok"])
        self.assertIn(REQUIRED_FILES[10], result["topology"]["required_files_missing"])

    def test_redirect_rejects_old_state_and_missing_redirect(self):
        for mutation in ("import {useReducer} from 'react'; redirect('/classes')", "export default function Old(){return null}"):
            with self.subTest(mutation=mutation):
                files = self.base()
                files[REQUIRED_FILES[0]] = mutation
                result = audit(self.tree(files))
                self.assertFalse(result["ok"])
                self.assertFalse(result["topology"]["legacy_preview_redirect_observed"])

    def test_static_dynamic_and_reexport_fixture_imports_fail(self):
        mutations = (
            "import '../../tests/fixtures/ClassesPreview/model'",
            "const x=import('tests/fixtures/data')",
            "export { x } from './fixtures/ClassesPreview/model'",
            "const x=require('tests/fixtures/data')",
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=mutation):
                files = self.base()
                path = f"apps/web/extensions/route66/production-{index}.ts"
                files[path] = mutation
                result = audit(self.tree(files))
                self.assertFalse(result["ok"])
                self.assertIn(path, result["topology"]["production_test_fixture_imports"])

    def test_fixture_files_themselves_remain_allowed(self):
        files = self.base()
        files["apps/web/extensions/route66/tests/fixtures/ClassesPreview/model.ts"] = "export const demo=true"
        self.assertTrue(audit(self.tree(files))["ok"])

    def test_malformed_source_fails(self):
        files = self.base()
        files[REQUIRED_FILES[5]] = b"\xff\xfe\x00"
        result = audit(self.tree(files))
        self.assertFalse(result["ok"])
        self.assertIn(REQUIRED_FILES[5], result["topology"]["malformed_sources"])

    def test_manifest_is_complete_and_dependency_ordered(self):
        self.assertEqual(validate_manifest(PHASE_MANIFEST), [])
        assigned = [item for phase in PHASE_MANIFEST for item in phase["audit_ids"]]
        self.assertEqual(set(assigned), set(AUDIT_CAPABILITIES))
        self.assertEqual(len(assigned), 52)
        positions = {phase["id"]: index for index, phase in enumerate(PHASE_MANIFEST)}
        for phase in PHASE_MANIFEST:
            for dependency in phase["depends_on"]:
                self.assertLess(positions[dependency], positions[phase["id"]])

    def test_manifest_rejects_invalid_missing_cyclic_and_reversed_dependencies(self):
        missing = copy.deepcopy(PHASE_MANIFEST)
        missing[1]["depends_on"] = ["LH-DOES-NOT-EXIST"]
        self.assertTrue(any("missing dependency" in error for error in validate_manifest(missing)))

        cyclic = copy.deepcopy(PHASE_MANIFEST)
        cyclic[0]["depends_on"] = ["LH-01"]
        cyclic_errors = validate_manifest(cyclic)
        self.assertTrue(any("cycle" in error for error in cyclic_errors))
        self.assertTrue(any("not earlier" in error for error in cyclic_errors))

        reversed_order = copy.deepcopy(PHASE_MANIFEST)
        reversed_order[1], reversed_order[2] = reversed_order[2], reversed_order[1]
        self.assertTrue(any("not earlier" in error for error in validate_manifest(reversed_order)))

    def test_manifest_rejects_missing_phase_assignment_and_unknown_audit(self):
        missing_assignment = copy.deepcopy(PHASE_MANIFEST)
        missing_assignment[1]["audit_ids"].remove("A07")
        self.assertTrue(any("unassigned audit IDs: A07" in error for error in validate_manifest(missing_assignment)))
        unknown = copy.deepcopy(PHASE_MANIFEST)
        unknown[1]["audit_ids"].append("Z99")
        self.assertTrue(any("unknown audit ID Z99" in error for error in validate_manifest(unknown)))

    def test_native_menu_blockers_only_appear_when_link_is_present(self):
        without = audit(self.tree(self.base()))
        self.assertEqual(without["topology"]["legacy_native_menu_links"], [])
        files = self.base()
        menu = "apps/web/components/Dashboard/Menus/DashLeftMenu.tsx"
        files[menu] = "<Link href='/dash/classes-preview'/>"
        with_link = audit(self.tree(files))
        self.assertEqual(with_link["topology"]["legacy_native_menu_links"], [menu])
        self.assertTrue(any("narrow prior review" in item for item in with_link["remaining_blockers"]))

    def test_cli_returns_nonzero_for_structural_failure(self):
        files = self.base()
        del files[REQUIRED_FILES[0]]
        root = self.tree(files)
        script = pathlib.Path(__file__).with_name("rehearse_goal.py")
        completed = subprocess.run([sys.executable, str(script), "--root", str(root)], capture_output=True, text=True)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('"ok": false', completed.stdout)


if __name__ == "__main__":
    unittest.main()
