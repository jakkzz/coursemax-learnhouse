"""Pure synthetic tests for the bounded NRRU course-export parser."""
import unittest
from types import SimpleNamespace

from src.route66_ext.services.nrru_course_roster import parse_course_roster


class CourseRosterParserTests(unittest.TestCase):
    cls = SimpleNamespace(academic_year=2569, semester=2, section="3",
                          registry_course_code="990001")

    @staticmethod
    def row(values):
        return b"".join(value.encode("cp874") + br"\cell " for value in values) + br"\row "

    def rtf(self, *, section="3", status="1", duplicate=False):
        metadata = self.row(["รายวิชา 990001", "ปีการศึกษา 2 / 2569"])
        header = self.row(["เลขที่", "รหัสประจำตัว", "ชื่อ", "เอก",
                           "กลุ่ม", "สถานภาพ", "จาก", "สัปดาห์"])
        student = self.row(["1", "6900000001", "นักศึกษา ตัวอย่าง", "สาขาตัวอย่าง",
                            section, status, "", ""] + [""] * 16)
        # The real export carries source facts in an RTF page header.  This
        # group must be rendered rather than treated like font/picture data.
        return br"{\rtf1\ansi " + br"{\header " + metadata + br"}" + header + student + (student if duplicate else b"") + b"}"

    def test_metadata_inside_header_is_validated_and_selected(self):
        rows = parse_course_roster(self.rtf(), self.cls)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["student_number"], "6900000001")
        self.assertEqual(rows[0]["faculty"], "")

    def test_exact_section_and_active_status_are_required(self):
        with self.assertRaisesRegex(ValueError, "No complete active roster"):
            parse_course_roster(self.rtf(section="4"), self.cls)
        with self.assertRaisesRegex(ValueError, "No complete active roster"):
            parse_course_roster(self.rtf(status="2"), self.cls)

    def test_duplicate_selected_student_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            parse_course_roster(self.rtf(duplicate=True), self.cls)

    def test_wrong_header_term_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "term"):
            parse_course_roster(self.rtf().replace(b"2569", b"2568"), self.cls)


if __name__ == "__main__":
    unittest.main()
