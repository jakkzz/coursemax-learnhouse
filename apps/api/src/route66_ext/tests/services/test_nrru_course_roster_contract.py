import unittest
from src.route66_ext.services import nrru_course_roster as parser


class Class:
    registry_course_code = "000204"
    academic_year = 2569
    semester = 1
    section = "P7"


def student(number="6500000001", name="คน ทดสอบ", section="P7", status="", ordinal="1", program=""):
    values = [ordinal, number, name, program, section, status, ""] + [""] * 17
    assert len(values) == 24
    return values


def esc(value):
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def make_rtf(data_rows=(), *, code="000204", term="1/2569", header=None,
             prefix="", suffix_rows=(), metadata_rows=True):
    rows = ([
        ["", "มหาวิทยาลัย", f"รายชื่อนักศึกษาในรายวิชาที่สอน ปีการศึกษา {term}", ""],
        [f"รายวิชา {code} เกมดิจิทัล หน่วยกิต 3 (2-2-5)", "", ""],
    ] if metadata_rows else []) + [
        list(header or ("เลขที่", "รหัสประจำตัว", "ชื่อ", "เอก", "กลุ่ม", "สถานภาพ", "จาก", "สัปดาห์", "")),
        *data_rows,
        *suffix_rows,
    ]
    table = []
    for row in rows:
        table.append("\\trowd " + "".join(esc(str(cell)) + "\\cell " for cell in row) + "\\row\n")
    return ("{\\rtf1\\ansi\\ansicpg874\\uc1 " + prefix + "".join(table) + "}").encode("cp874")


class CourseRosterTests(unittest.TestCase):
    def parse(self, content):
        return parser.parse_course_roster(content, Class())

    def test_multi_section_exact_isolation_and_contract(self):
        content = make_rtf([
            student("6500000001", "หนึ่ง", "P7", "", "2", ""),
            student("6500000002", "สอง", "P70", "0", "3", "วิชาเอก"),
            student("6500000003", "สาม", "p7", "1", "4", "โปรแกรม"),
        ])
        self.assertEqual(self.parse(content), [
            {"student_number": "6500000001", "full_name_th": "หนึ่ง", "faculty": "",
             "program": "", "registry_status_code": None, "display_position": 2},
            {"student_number": "6500000003", "full_name_th": "สาม", "faculty": "",
             "program": "โปรแกรม", "registry_status_code": "1", "display_position": 4},
        ])

    def test_same_id_other_section_is_allowed(self):
        rows = [student("6500000001", section="P70"), student("6500000001", section="P7", ordinal="2")]
        self.assertEqual(len(self.parse(make_rtf(rows))), 1)

    def test_supported_widths_header_metadata_and_final_par(self):
        header = ("เลขที่", "รหัสประจำตัว", "ชื่อ", "เอก", "กลุ่ม", "สถานภาพ", "จาก") + ("สัปดาห์",) * 16
        content = make_rtf([student()[:-1]], header=header)
        self.assertEqual(len(self.parse(content[:-1] + b"\\par}")), 1)
        with self.assertRaisesRegex(ValueError, "Incomplete registrar student row"):
            self.parse(make_rtf([student()[:-1] + ["not-empty"]]))

    def test_wrong_term_course_header_and_student_number(self):
        bad = [
            make_rtf([student()], term="2/2569"),
            make_rtf([student()], code="0002040"),
            make_rtf([student()], header=("ลำดับ", "รหัสประจำตัว", "ชื่อ", "เอก", "กลุ่ม", "สถานภาพ", "จาก", "สัปดาห์")),
            make_rtf([student(number="650000001")]),
            make_rtf([student(ordinal="x")]),
        ]
        for content in bad:
            with self.subTest(content=content[:80]), self.assertRaises(ValueError):
                self.parse(content)

    def test_duplicate_selected_active_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.parse(make_rtf([student(), student(ordinal="2")]))

    def test_escaped_literals_hex_unicode_and_group_scoped_uc(self):
        # Name combines literal RTF metacharacters, CP874 hex, and Unicode with
        # one fallback byte. Nested uc0 is restored to uc1 after its group.
        thai_hex = "".join("\\'%02x" % b for b in "ก".encode("cp874"))
        encoded_name = r"ชื่อ \{A\}\\ " + thai_hex + r" \u3585? {\uc0\u3586}\u3587?"
        row = student(name="TOKEN")
        content = make_rtf([row]).replace(b"TOKEN", encoded_name.encode("cp874"))
        result = self.parse(content)
        self.assertEqual(result[0]["full_name_th"], "ชื่อ {A}\\ ก ก ขฃ")

    def test_pict_and_star_destination_are_skipped(self):
        prefix = r"{\fonttbl{\f0 fake}}{\pict 1234abcd}{\*\unknown hidden}"
        self.assertEqual(len(self.parse(make_rtf([student()], prefix=prefix))), 1)

    def test_binary_payload_is_rejected_even_in_skipped_destination(self):
        with self.assertRaisesRegex(ValueError, "Binary"):
            self.parse(make_rtf([student()], prefix=r"{\pict\bin4 abcd}"))

    def test_unknown_status_is_rejected_before_section_filter(self):
        with self.assertRaisesRegex(ValueError, "status"):
            self.parse(make_rtf([student(section="P70", status="9"), student(ordinal="2")]))

    def test_withdrawn_and_moved_out_are_excluded(self):
        rows = [student(status="2"), student("6500000002", status="4", ordinal="2"),
                student("6500000003", status="5", ordinal="3")]
        result = self.parse(make_rtf(rows))
        self.assertEqual([r["student_number"] for r in result], ["6500000003"])
        self.assertEqual(result[0]["registry_status_code"], "5")

    def test_no_active_source_records_is_rejected(self):
        for rows in ([], [student(section="P70")], [student(status="2")]):
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, "No complete"):
                self.parse(make_rtf(rows))

    def test_footer_digits_are_not_students(self):
        content = make_rtf([student()], suffix_rows=[["2569"] + [""] * 23])
        self.assertEqual(len(self.parse(content)), 1)

    def test_truncated_malformed_and_markup_only_rtf(self):
        malformed = [
            make_rtf([student()])[:-1],
            b"{\\rtf1 \\'a}",
            b"{\\rtf1 \\u3585}",
            b"{\\rtf1}",
            b"plain text",
            b"{\\rtf1 {oops}} trailing",
        ]
        for content in malformed:
            with self.subTest(content=content), self.assertRaises(ValueError):
                self.parse(content)

    def test_no_section_and_size_limit(self):
        old = Class.section
        try:
            Class.section = "  "
            with self.assertRaisesRegex(ValueError, "section"):
                self.parse(make_rtf([student()]))
        finally:
            Class.section = old
        with self.assertRaisesRegex(ValueError, "size"):
            self.parse(b"x" * (parser.MAX_BYTES + 1))

    def test_ambiguous_official_metadata_is_rejected(self):
        content = make_rtf([student()])
        duplicate_term = content.replace("รายวิชา".encode("cp874"),
                                         "ปีการศึกษา 1/2569 รายวิชา".encode("cp874"), 1)
        with self.assertRaisesRegex(ValueError, "term"):
            self.parse(duplicate_term)


if __name__ == "__main__":
    unittest.main()
