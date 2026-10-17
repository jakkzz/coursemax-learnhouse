"""Deterministic NRRU calendar text reader; synthetic semester 1/2570 in the official layout."""
from datetime import date
import unittest

from src.route66_ext.services import calendar_plan as planner
from src.route66_ext.services import nrru_calendar_pdf as reader

THAI = str.maketrans('0123456789', '๐๑๒๓๔๕๖๗๘๙')

ANNOUNCEMENT = """ประกาศมหาวิทยาลัยราชภัฏนครราชสีมา
เรื่อง ปฏิทินการเรียนการสอนสำหรับนักศึกษาภาคปกติ
ประจำภาคการศึกษาที่ 1 ปการศึกษา 2570
12 กรกฎาคม 2570 เปิดภาคการศึกษาที่ 1 ปีการศึกษา 2570
28 กรกฎาคม 2570 วันหยุด วันสมมุติหนึ่ง
6 สิงหาคม 2570 วันหยุด วันสมมุติสอง
9 สิงหาคม 2570 กิจกรรมทดสอบผู้เรียนระหว่างภาค
30 สิงหาคม 2570 – 3 กันยายน 2570 งดการเรียนการสอน เนื่องจากกิจกรรมมหาวิทยาลัย"""

MAKEUPS = """จันทร์ที่ 13 กันยายน 2570 วันสอนชดเชยวันพุธที่ 28 กรกฎาคม 2570
อังคารที่ 14 กันยายน 2570 วันสอนชดเชยวันศุกร์ที่ 6 สิงหาคม 2570
พุธที่ 15 กันยายน 2570 วันสอนชดเชยวันจันทร์ที่ 30 สิงหาคม 2570
พฤหัสบดีที่ 16 กันยายน 2570 วันสอนชดเชยวันอังคารที่ 31 สิงหาคม 2570
ศุกรที่ 17 กันยายน 2570 วันสอนชดเชยวันพุธที่ 1 กันยายน 2570
จันทร์ที่ 20 กันยายน 2570 วันสอนชดเชยวันพฤหัสบดีที่ 2 กันยายน 2570
อังคารที่ 21 กันยายน 2570 วันสอนชดเชยวันศุกร์ที่ 3 กันยายน 2570
วันสุดท้ายของการเรียนการสอน ภาคการศึกษาที่ 1 ปีการศึกษา 2570
สอบปลายภาค ประจำภาคการศึกษาที่ 1 ปีการศึกษา 2570 22 – 28 กันยายน 2570
27 กันยายน 2570 เปิดภาคการศึกษาที่ 2 ปีการศึกษา 2570
5 ธันวาคม 2570 วันหยุด วันสมมุติสาม"""

# Week table: odd/even labels deliberately differ from week-number parity; one original year is mistyped.
TABLE = """การกำหนดสัปดาห์เรียนคี่ – คู่
ภาคปกติ ภาคการศึกษาที่ 1/2570
สัปดาห์คี่ ครั้งที่ 1 สัปดาห์ที่ 1 วันที่ 12 – 16 กรกฎาคม 2570
ครั้งที่ 2 สัปดาหที่ 3 วันที่ 26 – 27, 29 – 30 กรกฎาคม 2570
ครั้งที่ 3 สัปดาห์ที่ 7 วันที่ 23 – 27 สิงหาคม 2570
ครั้งที่ 4 สัปดาห์ที่ 9 วันที่ 6 – 10 กันยายน 2570
สัปดาห์สอนชดเชย วันที่ 28 กรกฎาคม 2570 วันสอนชดเชยวันจันทร์ที่ 13 กันยายน 2570
สัปดาห์คู่ ครั้งที่ 1 สัปดาห์ที่ 2 วันที่ 19 – 23 กรกฎาคม 2570
ครั้งที่ 2 สัปดาห์ที่ 4 วันที่ 2 – 5 สิงหาคม 2570
ครั้งที่ 3 สัปดาห์ที่ 6 วันที่ 16 – 20 สิงหาคม 2570
ครั้งที่ 4 สัปดาห์ที่ 8 งดการเรียนการสอน เนื่องจากกิจกรรมมหาวิทยาลัย
สัปดาห์สอนชดเชย วันที่ 6 สิงหาคม 2569 วันสอนชดเชยวันอังคารที่ 14 กันยายน 2570
หมายเหตุ สัปดาห์ที่ 5 วันที่ 9 – 13 สิงหาคม 2570 กิจกรรมทดสอบผู้เรียนระหว่างภาค"""


# Abridged side-by-side program comparison (ฉบับย่อ): registration rows only, no teaching weeks.
ABRIDGED = """ปฏิทินการศึกษาระดับปริญญาตรี มหาวิทยาลัยสมมุติ ภาคเรียนที่ ๒/๒๕๗๑ (ฉบับย่อ)
ที่ กิจกรรม
ภาคปกติ (ค.บ.)
ลงทะเบียนปฏิบัติ
การวิชาชีพ
ภาคพิเศษ ภาค กศ.ปช.
1 วันเปิดภาคการศึกษา 3 ธ.ค. 71 10 ธ.ค. 71 17 ธ.ค. 71
2 สอบปลายภาค – 1 – 5 มี.ค. 72 8 – 9 มี.ค. 72"""


def abridged_pages():
    return [{'page': 1, 'text': ABRIDGED}, {'page': 2, 'text': 'ปฏิทินการศึกษา (ต่อ)\n3 วันปิดภาคการศึกษา – 12 มี.ค. 72'}]


def pages(thai_digits=True):
    texts = [ANNOUNCEMENT, MAKEUPS, TABLE]
    convert = (lambda t: t.translate(THAI)) if thai_digits else (lambda t: t)
    return [{'page': n, 'text': convert(t) if n < 3 else t} for n, t in enumerate(texts, 1)]


class ReaderTests(unittest.TestCase):
    def test_reads_semester_weeks_closures_and_makeups_from_explicit_labels(self):
        result = reader.read(pages(), 2570)
        self.assertEqual(result['method'], 'nrru_calendar_text_v1')
        payload = result['payload']
        self.assertEqual(len(payload.terms), 1)  # the next-term opening is a reference, not a semester
        term = payload.terms[0]
        self.assertEqual((term.semester, term.starts_on, term.ends_on, term.page), (1, date(2027, 7, 12), date(2027, 9, 21), 1))
        self.assertEqual({w.number: w.rotation for w in term.weeks},
                         {1: 'odd', 2: 'even', 3: 'odd', 4: 'even', 5: 'midterm', 6: 'even', 7: 'odd', 8: 'even', 9: 'odd'})
        weeks = {w.number: w for w in term.weeks}
        self.assertEqual((weeks[3].starts_on, weeks[3].ends_on), (date(2027, 7, 26), date(2027, 7, 30)))
        self.assertEqual(weeks[4].ends_on, date(2027, 8, 6))  # listed days omit the Friday holiday
        self.assertEqual((weeks[5].teaching, weeks[5].uncertain, weeks[5].note), (True, True, 'กิจกรรมทดสอบผู้เรียนระหว่างภาค'))
        self.assertEqual((weeks[8].starts_on, weeks[8].ends_on, weeks[8].teaching, weeks[8].uncertain),
                         (date(2027, 8, 30), date(2027, 9, 3), False, False))
        self.assertTrue(all(w.teaching for n, w in weeks.items() if n != 8))
        self.assertTrue(all(not w.uncertain for n, w in weeks.items() if n != 5))
        self.assertEqual([(c.affected_on, c.makeup_on, c.page) for c in term.closures], [
            (date(2027, 7, 28), date(2027, 9, 13), 1), (date(2027, 8, 6), date(2027, 9, 14), 1),
            (date(2027, 8, 30), date(2027, 9, 15), 1), (date(2027, 8, 31), date(2027, 9, 16), 1),
            (date(2027, 9, 1), date(2027, 9, 17), 1), (date(2027, 9, 2), date(2027, 9, 20), 1),
            (date(2027, 9, 3), date(2027, 9, 21), 1)])
        self.assertEqual(term.closures[0].note, 'วันหยุด วันสมมุติหนึ่ง')
        # The table's conflicting original year is a review question; page 2 evidence stays in the draft.
        self.assertEqual(len(payload.unresolved), 1)
        self.assertEqual(payload.unresolved[0], 'หน้า 3 และหน้า 2 ระบุวันเดิมของการสอนชดเชย 1 รายการไม่ตรงกัน ร่างนี้ใช้หน้า 2 '
                         'โปรดยืนยันวันเดิม / Pages 3 and 2 disagree on the original date of 1 make-ups; the draft uses page 2. '
                         'Confirm the original dates')
        self.assertTrue(any('6 สิงหาคม 2569 vs 6 สิงหาคม 2570' in n for n in result['notes']))
        self.assertEqual(sorted(planner.issues(payload, 3)), sorted(['Unresolved: ' + payload.unresolved[0], 'Semester 1 week 5: marked uncertain']))
        self.assertTrue(any('Week 8 has no teaching' in n for n in result['notes']))
        self.assertTrue(any('outside this semester' in n for n in result['notes']))

    def test_arabic_digits_read_identically_and_plan_keeps_original_weeks(self):
        thai, arabic = reader.read(pages(), 2570), reader.read(pages(thai_digits=False), 2570)
        self.assertEqual(thai['payload'], arabic['payload'])
        rows, _, errors = planner.plan(thai['payload'], 1, [{'day': 'พุธ', 'start_time': '9:00', 'end_time': '12:00'}], 'onsite', 'X')
        self.assertEqual(errors, [])
        self.assertEqual([(r['academic_week'], r['calendar_kind'], r['state'], r['starts_at'].date()) for r in rows
                          if r['academic_week'] in (3, 5, 8)], [
            (3, 'regular', 'no_class', date(2027, 7, 28)), (5, 'regular', 'scheduled', date(2027, 8, 11)),
            (8, 'regular', 'no_class', date(2027, 9, 1)), (3, 'makeup', 'scheduled', date(2027, 9, 13)),
            (8, 'makeup', 'scheduled', date(2027, 9, 17))])

    def test_review_questions_for_year_and_weekday_mismatches(self):
        result = reader.read(pages(), 2571)
        self.assertTrue(any('academic year 2570' in u for u in result['payload'].unresolved))
        wrong = pages()
        wrong[1]['text'] = wrong[1]['text'].replace('จันทร์ที่ ๑๓ กันยายน', 'อังคารที่ ๑๓ กันยายน')
        self.assertTrue(any('not the weekday' in u for u in reader.read(wrong, 2570)['payload'].unresolved))

    def test_other_layouts_fall_back_to_native_reader(self):
        self.assertIsNone(reader.read([], 2570))
        self.assertIsNone(reader.read([{'page': 1, 'text': 'Academic calendar 2027 semester 1'}], 2570))
        no_table = pages()[:2]
        self.assertIsNone(reader.read(no_table, 2570))
        other_school = [dict(p, text=p['text'].replace('ราชภัฏนครราชสีมา', 'ตัวอย่าง')) for p in pages()]
        self.assertIsNone(reader.read(other_school, 2570))

    def test_legacy_font_glyphs_become_standard_thai(self):
        samples = {'เป\uf701ด': 'เปิด', 'ป\uf702': 'ปี', 'ฝ\uf703ก': 'ฝึก', 'ส\uf70aง': 'ส่ง', 'เว\uf70bน': 'เว้น',
                   'สัปดาห\uf70e': 'สัปดาห์', 'เป\uf712น': 'เป็น', 'ป\uf713า': 'ป่า', 'ป\uf717': 'ป์'}
        for raw, expected in samples.items():
            self.assertEqual(raw.translate(reader._GLYPHS), expected)
        text = pages()
        text[0]['text'] = text[0]['text'].replace('วันหยุด วันสมมุติหนึ่ง', 'วันหยุด วันเป\uf712นสมมุติ')
        self.assertEqual(reader.read(text, 2570)['payload'].terms[0].closures[0].note, 'วันหยุด วันเป็นสมมุติ')

    def test_metadata_from_header_only_with_filename_fallback(self):
        text = pages()
        text[1]['text'] += '\nนักศึกษาที่ลงทะเบียนเรียนข้ามภาคกับนักศึกษาภาค กศ.ปช.'  # later cross-program reference
        self.assertEqual(reader.metadata(text, 'x.pdf'),
                         {'academic_year': 2570, 'track': 'ภาคปกติ', 'name': 'ปฏิทินการเรียนการสอน ภาคปกติ ปีการศึกษา 2570'})
        evening = [{'page': 1, 'text': 'ปฏิทินการศึกษา สำหรับนักศึกษาภาค กศ.ปช.\nปีการศึกษา ๒๕๗๑\n๑ มิถุนายน ๒๕๗๑ ภาคปกติ'}]
        self.assertEqual(reader.metadata(evening)['academic_year'], 2571)
        self.assertEqual(reader.metadata(evening)['track'], 'ภาค กศ.ปช.')
        unknown = reader.metadata([{'page': 1, 'text': 'Calendar notes'}], 'Term_calendar.PDF')
        self.assertEqual(unknown, {'academic_year': None, 'track': None, 'name': 'Term calendar'})

    def test_abridged_multi_program_source_is_kept_without_choosing_a_program(self):
        source = abridged_pages()
        found = reader.abridged(source)
        self.assertEqual((found['kind'], found['semester'], found['academic_year']), ('abridged_multi_program', 2, 2571))
        # The practicum column keeps its full label; it is never reported as an ordinary program.
        self.assertEqual(found['programs'], ['ภาคปกติ (ค.บ.) ลงทะเบียนปฏิบัติการวิชาชีพ', 'ภาคพิเศษ', 'ภาค กศ.ปช.'])
        self.assertEqual(reader.metadata(source, 'MIX.pdf'), {'academic_year': 2571, 'track': 'ฉบับรวมหลายรูปแบบ',
            'name': 'ปฏิทินการศึกษาระดับปริญญาตรี มหาวิทยาลัยสมมุติ ภาคเรียนที่ 2/2571 (ฉบับย่อ รวมหลายรูปแบบ)'})
        self.assertIsNone(reader.read(source, 2571))  # no weeks or dates are generated
        # Full calendars and a single-program abridged header are unaffected.
        self.assertIsNone(reader.abridged(pages()))
        single = [{'page': 1, 'text': ABRIDGED.replace('ภาคพิเศษ ภาค กศ.ปช.', '')
                   .replace('ภาคปกติ (ค.บ.)\nลงทะเบียนปฏิบัติ\nการวิชาชีพ\n', 'ภาคปกติ\n')}]
        self.assertIsNone(reader.abridged(single))
        self.assertNotEqual(reader.metadata(single)['track'], 'ฉบับรวมหลายรูปแบบ')

    def test_date_lists(self):
        self.assertEqual(reader.dates('10 – 11, 13 – 14 สิงหาคม 2569'),
                         [date(2026, 8, d) for d in (10, 11, 13, 14)])
        self.assertEqual(reader.dates('28 – 30 กันยายน 2569, 1 – 2 ตุลาคม 2569'),
                         [date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2)])
        self.assertEqual(reader.dates('30 กันยายน 2569 – 2 ตุลาคม 2569'),
                         [date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2)])
        self.assertEqual(reader.thai(date(2026, 10, 5)), '5 ตุลาคม 2569')


if __name__ == '__main__':
    unittest.main()
