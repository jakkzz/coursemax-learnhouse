"""Offline advisory mapping contract; no database, registrar or native imports."""
import copy
import unittest

from src.route66_ext.services.mapping_dry_run import plan_mapping


def fixture():
    target = dict(course_id=17, teacher_id=9, registry_course_id="123",
                  academic_year=2569, semester=1, section="S1")
    catalog = {
        "courses": [dict(id=17, registry_course_id="123", course_code="SYNTHETIC", name="Synthetic course")],
        "teaching_assignments": [dict(course_id=17, user_id=9, active=True)],
        "can_assign_teachers": True,
    }
    projection = {"classes": [dict(id=4, course_id=17, registry_course_id="123",
                                  academic_year=2569, semester=1, section="S1", manageable=True)]}
    return target, catalog, projection


class MappingDryRunTests(unittest.TestCase):
    def check(self, args, status, next_step=None):
        result = plan_mapping(*args)
        self.assertEqual(result["status"], status)
        if next_step:
            self.assertEqual(result["next_step"], next_step)
        self.assertIs(result["authorization_granted"], False)
        self.assertEqual(result["writes_performed"], 0)
        self.assertEqual(set(result), {"status", "next_step", "class_id", "course_id",
                                      "writes_performed", "authorization_granted"})
        if status != "linked":
            self.assertIsNone(result["class_id"])
        return result

    def test_exact_link_is_advisory_not_authorization(self):
        self.assertEqual(self.check(fixture(), "linked", "review_roster_preview")["class_id"], 4)

    def test_invalid_targets(self):
        for key, values in {
            "course_id": [True, False, 0, -1, "17", None, 17.0],
            "teacher_id": [True, 0, "9"],
            "registry_course_id": ["", "0", "0123", "123 ", "x", "1" * 21, 123, None],
            "academic_year": [True, "2569", 2499, 2701],
            "semester": [True, "1", 0, 4],
            "section": ["", " S1", "S1 ", "!", "a" * 41, None],
        }.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    args = fixture(); args[0][key] = value
                    self.check(args, "invalid_input", "review_input")
        for value in [None, [], "not a target"]:
            self.check((value, *fixture()[1:]), "invalid_input")

    def test_malformed_collection_shapes(self):
        for index, key, values in [
            (1, "courses", [None, {}, [None], [{"id": True}], [{"id": 17}]]),
            (1, "teaching_assignments", [None, {}, [None], [{}]]),
            (1, "can_assign_teachers", [None, 1, "true"]),
            (2, "classes", [None, {}, [None], [{}]]),
        ]:
            for value in values:
                with self.subTest(index=index, key=key, value=value):
                    args = fixture(); args[index][key] = value
                    self.check(args, "invalid_input")
        for index in [1, 2]:
            args = list(fixture()); args[index] = None
            self.check(args, "invalid_input")

    def test_missing_course_is_not_empty_registrar_roster(self):
        args = fixture(); args[1]["courses"] = []
        self.check(args, "course_unavailable", "select_existing_course")

    def test_duplicate_selected_catalog_id_requires_review(self):
        args = fixture(); args[1]["courses"].append(copy.deepcopy(args[1]["courses"][0]))
        self.check(args, "review_required", "review_ambiguity")

    def test_real_api_null_binding_and_code_are_unconfigured(self):
        args = fixture(); args[1]["courses"][0].update(registry_course_id=None, course_code=None)
        self.check(args, "mapping_required", "administrator_review")

    def test_empty_binding_is_unconfigured(self):
        args = fixture(); args[1]["courses"][0]["registry_course_id"] = ""
        self.check(args, "mapping_required")

    def test_conflicting_binding_never_reassigns(self):
        args = fixture(); args[1]["courses"][0]["registry_course_id"] = "999"
        self.check(args, "mapping_conflict", "administrator_review")

    def test_missing_assignment_requires_review_even_for_admin(self):
        for admin in [True, False]:
            args = fixture(); args[1]["can_assign_teachers"] = admin
            args[1]["teaching_assignments"] = []
            self.check(args, "assignment_review_required", "administrator_review")

    def test_inactive_assignment_requires_review(self):
        args = fixture(); args[1]["teaching_assignments"][0]["active"] = False
        self.check(args, "assignment_review_required")

    def test_unrelated_assignment_cannot_establish_selected_teacher(self):
        for key, value in [("course_id", 22), ("user_id", 10)]:
            args = fixture(); args[1]["teaching_assignments"][0][key] = value
            self.check(args, "assignment_review_required")

    def test_duplicate_assignment_including_inactive_is_ambiguous(self):
        args = fixture(); row = dict(args[1]["teaching_assignments"][0], active=False)
        args[1]["teaching_assignments"].append(row)
        self.check(args, "review_required", "review_ambiguity")

    def test_assignment_boolean_must_be_strict(self):
        for value in [1, "true", None]:
            args = fixture(); args[1]["teaching_assignments"][0]["active"] = value
            self.check(args, "invalid_input")

    def test_empty_projection_requires_reviewed_setup_not_import(self):
        args = fixture(); args[2]["classes"] = []
        self.check(args, "class_setup_required", "review_class_setup")

    def test_term_section_and_official_id_are_exact(self):
        for key, value in [("academic_year", 2570), ("semester", 2), ("section", "s1"),
                           ("registry_course_id", "999")]:
            args = fixture(); args[2]["classes"][0][key] = value
            self.check(args, "class_setup_required")

    def test_wrong_type_identity_fields_are_not_a_missing_class(self):
        for key, value in [("academic_year", "2569"), ("semester", True),
                           ("course_id", True), ("registry_course_id", 123), ("section", None)]:
            args = fixture(); args[2]["classes"][0][key] = value
            self.check(args, "invalid_input")

    def test_hidden_duplicate_is_counted_before_id_and_manageability(self):
        for class_id, manageable in [(5, False), ("bad", False), (True, True), (None, "true")]:
            args = fixture(); duplicate = dict(args[2]["classes"][0], id=class_id, manageable=manageable)
            args[2]["classes"].insert(0, duplicate)
            self.check(args, "review_required", "review_ambiguity")

    def test_duplicate_on_other_selected_course_is_still_ambiguous(self):
        args = fixture(); args[2]["classes"].append(dict(args[2]["classes"][0], id=5, course_id=22))
        self.check(args, "review_required", "review_ambiguity")

    def test_single_class_id_must_be_strict_positive_integer(self):
        for value in [True, False, 0, -1, "4", None, 4.0]:
            args = fixture(); args[2]["classes"][0]["id"] = value
            self.check(args, "review_required", "review_class_authority")

    def test_manageability_must_be_strict_true(self):
        for value in [False, 1, "true", None]:
            args = fixture(); args[2]["classes"][0]["manageable"] = value
            self.check(args, "review_required", "review_class_authority")

    def test_single_wrong_native_course_cannot_link(self):
        args = fixture(); args[2]["classes"][0]["course_id"] = 22
        self.check(args, "review_required", "review_class_authority")

    def test_unrelated_unmatched_school_class_does_not_poison_mapping(self):
        args = fixture()
        args[2]["classes"].append(dict(args[2]["classes"][0], id=5, course_id=None,
                                       registry_course_id="999"))
        self.check(args, "linked", "review_roster_preview")

    def test_unmatched_exact_class_requires_review_not_automatic_linking(self):
        args = fixture(); args[2]["classes"][0]["course_id"] = None
        self.check(args, "review_required", "review_class_authority")

    def test_unmatched_exact_duplicate_is_still_ambiguous(self):
        args = fixture()
        args[2]["classes"].append(dict(args[2]["classes"][0], id=5, course_id=None))
        self.check(args, "review_required", "review_ambiguity")

    def test_duplicate_titles_and_registrar_ids_do_not_merge_courses_17_and_22(self):
        args = fixture(); args[1]["courses"].append(dict(args[1]["courses"][0], id=22))
        self.check(args, "linked")
        args[0]["course_id"] = 22
        args[1]["teaching_assignments"].append(dict(course_id=22, user_id=9, active=True))
        self.check(args, "review_required", "review_class_authority")

    def test_missing_class_identity_field_is_malformed(self):
        for key in ["course_id", "registry_course_id", "academic_year", "semester", "section"]:
            args = fixture(); del args[2]["classes"][0][key]
            self.check(args, "invalid_input")

    def test_redacted_student_class_is_not_a_match(self):
        args = fixture(); args[2]["classes"][0].update(registry_course_id=None, manageable=False)
        self.check(args, "class_setup_required", "review_class_setup")

    def test_projection_cannot_override_missing_mapping(self):
        args = fixture(); args[1]["courses"][0]["registry_course_id"] = None
        self.check(args, "mapping_required")

    def test_metadata_does_not_establish_identity_or_authority(self):
        args = fixture(); args[0].update(name="Someone", email="synthetic@example.invalid", is_superadmin=True)
        args[1]["courses"][0].update(name="Unrelated", course_code="IGNORED")
        self.check(args, "linked")
        args[1]["teaching_assignments"] = []
        self.check(args, "assignment_review_required")

    def test_inputs_remain_deeply_immutable_and_repeats_deterministic(self):
        args = fixture(); before = copy.deepcopy(args)
        self.assertEqual(plan_mapping(*args), plan_mapping(*args))
        self.assertEqual(args, before)


if __name__ == "__main__":
    unittest.main()
