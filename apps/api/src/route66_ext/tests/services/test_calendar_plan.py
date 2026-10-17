"""Pure deterministic calendar planner cases; synthetic dates only."""
from datetime import date, timedelta
import unittest
from src.route66_ext.services import calendar_plan as p

MON = date(2026, 6, 22)  # a Monday


def week(n, rotation='teaching', teaching=True, start=None):
    start = start or MON + timedelta(weeks=n - 1)
    return {'number': n, 'starts_on': start.isoformat(), 'ends_on': (start + timedelta(days=6)).isoformat(),
            'rotation': rotation, 'teaching': teaching}


def payload(weeks, closures=(), semester=1):
    return p.Payload.model_validate({'terms': [{'semester': semester, 'starts_on': MON.isoformat(),
        'ends_on': (MON + timedelta(weeks=len(weeks)) - timedelta(days=1)).isoformat(),
        'weeks': weeks, 'closures': list(closures)}]})


MEETINGS = [{'day': 'จันทร์', 'start_time': '9:00', 'end_time': '12:00', 'details': 'ROOM-1'},
            {'day': 'พฤหัสบดี', 'start_time': '13:00', 'end_time': '15:00', 'details': 'LAB-2'}]


class PlannerTests(unittest.TestCase):
    def run_plan(self, data, pattern='onsite', meetings=MEETINGS):
        return p.plan(data, 1, meetings, pattern, '990001 P1')

    def test_multiple_slots_and_dates(self):
        rows, warnings, errors = self.run_plan(payload([week(1), week(2)]))
        self.assertEqual(errors, [])
        self.assertEqual([(r['academic_week'], r['slot_key'], r['nominal_on']) for r in rows], [
            (1, 'mon-0900-1200', MON), (1, 'thu-1300-1500', MON + timedelta(days=3)),
            (2, 'mon-0900-1200', MON + timedelta(days=7)), (2, 'thu-1300-1500', MON + timedelta(days=10))])
        self.assertEqual(rows[0]['starts_at'].isoformat(), '2026-06-22T02:00:00+00:00')
        self.assertEqual(rows[1]['location'], 'LAB-2')

    def test_explicit_rotation_exam_week_then_even(self):
        weeks = [week(7, 'odd'), week(8, 'midterm', False), week(9, 'even')]
        rows, _, errors = self.run_plan(payload(weeks), 'even_onsite', MEETINGS[:1])
        self.assertEqual(errors, [])
        self.assertEqual([(r['academic_week'], r['rotation'], r['mode']) for r in rows],
                         [(7, 'odd', 'online'), (9, 'even', 'onsite')])

    def test_reviewed_exam_week_with_classes_is_kept(self):
        rows, _, _ = self.run_plan(payload([week(1), week(2, 'midterm', True)]), meetings=MEETINGS[:1])
        self.assertEqual([r['academic_week'] for r in rows], [1, 2])

    def test_alternating_pattern_requires_explicit_rotation(self):
        rows, _, errors = self.run_plan(payload([week(1, 'teaching')]), 'even_onsite')
        self.assertTrue(errors)
        self.assertEqual(rows, [])

    def test_hybrid_first_mode_generates_weekly_dates_and_keeps_makeup_mode(self):
        source = payload([week(n) for n in range(1, 5)], [
            {'affected_on': MON.isoformat(), 'makeup_on': (MON + timedelta(weeks=5, days=5)).isoformat(), 'note': 'closed'}])
        before = source.model_dump(mode='json')
        for start in ('onsite', 'online'):
            rows, _, errors = p.plan(source, 1, MEETINGS, 'even_onsite', 'fixture', start)
            self.assertEqual(errors, [])
            other = 'online' if start == 'onsite' else 'onsite'
            self.assertEqual({(r['academic_week'], r['mode']) for r in rows},
                             {(1, start), (2, other), (3, start), (4, other)})
            makeup = next(r for r in rows if r['calendar_kind'] == 'makeup')
            self.assertEqual((makeup['academic_week'], makeup['makeup_for'], makeup['mode']), (1, MON, start))
            self.assertEqual({r['rotation'] for r in rows}, {'teaching'})  # no invented school rotation
        self.assertEqual(source.model_dump(mode='json'), before)
        self.assertTrue(p.plan(source, 1, MEETINGS, 'even_onsite', 'fixture', 'other')[2])

    def test_hybrid_respects_reviewed_school_rotation_instead_of_week_number_parity(self):
        source = payload([week(7, 'odd'), week(8, 'midterm', False), week(9, 'even')])
        rows, _, errors = p.plan(source, 1, MEETINGS[:1], 'even_onsite', 'fixture', 'online')
        self.assertEqual(errors, [])
        self.assertEqual([(r['academic_week'], r['mode']) for r in rows], [(7, 'online'), (9, 'onsite')])
        inverse, _, _ = p.plan(source, 1, MEETINGS[:1], 'even_onsite', 'fixture', 'onsite')
        self.assertEqual([(r['academic_week'], r['mode']) for r in inverse], [(7, 'onsite'), (9, 'online')])
        self.assertNotEqual(p.fingerprint(rows), p.fingerprint(inverse))

    def test_hybrid_does_not_restart_after_a_filtered_or_cancelled_week(self):
        source = payload([week(n) for n in range(1, 5)],
                         [{'affected_on': (MON + timedelta(weeks=1)).isoformat(), 'note': 'holiday'}])
        meetings = [dict(MEETINGS[0], details='W:(2-4)')]
        rows, _, errors = p.plan(source, 1, meetings, 'even_onsite', 'fixture', 'online')
        self.assertEqual(errors, [])
        self.assertEqual([(r['academic_week'], r['mode'], r['state']) for r in rows],
                         [(2, 'onsite', 'no_class'), (3, 'online', 'scheduled'), (4, 'onsite', 'scheduled')])

    def test_closure_without_and_with_makeup_keeps_original_week(self):
        saturday = MON + timedelta(weeks=5, days=5)  # outside week 1, a weekend
        data = payload([week(1), week(2)], [
            {'affected_on': MON.isoformat(), 'makeup_on': saturday.isoformat(), 'note': 'วันหยุด'},
            {'affected_on': (MON + timedelta(days=10)).isoformat(), 'makeup_on': None, 'note': 'ปิดเรียน'}])
        rows, warnings, errors = self.run_plan(data)
        self.assertEqual(errors, [])
        cancelled = [(r['academic_week'], r['calendar_kind'], r['state']) for r in rows if r['state'] == 'no_class']
        self.assertEqual(cancelled, [(1, 'regular', 'no_class'), (2, 'regular', 'no_class')])
        makeup = [r for r in rows if r['calendar_kind'] == 'makeup']
        self.assertEqual(len(makeup), 1)
        self.assertEqual((makeup[0]['academic_week'], makeup[0]['makeup_for'], makeup[0]['slot_key']),
                         (1, MON, 'mon-0900-1200'))
        self.assertEqual(makeup[0]['starts_at'].date(), saturday)
        self.assertTrue(any('weekend' in w for w in warnings))
        self.assertTrue(any('outside the term' in w for w in warnings))

    def test_non_teaching_week_plans_only_explicit_closures_and_their_makeups(self):
        closed = MON + timedelta(weeks=1)  # Monday of week 2, which has no teaching
        makeup = MON + timedelta(weeks=2, days=2)
        data = payload([week(1), week(2, 'even', False), week(3)],
                       [{'affected_on': closed.isoformat(), 'makeup_on': makeup.isoformat(), 'note': 'งดการเรียนการสอน'}])
        rows, _, errors = self.run_plan(data)
        self.assertEqual(errors, [])
        self.assertEqual([(r['slot_key'][:3], r['calendar_kind'], r['state'], r['starts_at'].date()) for r in rows
                          if r['academic_week'] == 2],
                         [('mon', 'regular', 'no_class', closed), ('mon', 'makeup', 'scheduled', makeup)])
        # The official W: filter still applies by original week: outside it, no closure or make-up row.
        outside = [dict(MEETINGS[0], details='W:(1,3)')]
        rows, _, _ = self.run_plan(data, meetings=outside)
        self.assertEqual({r['academic_week'] for r in rows}, {1, 3})

    def test_closure_on_non_meeting_weekday_does_not_apply(self):
        data = payload([week(1)], [{'affected_on': (MON + timedelta(days=1)).isoformat(), 'note': 'Tuesday'}])
        rows, _, _ = self.run_plan(data)
        self.assertTrue(all(r['state'] == 'scheduled' for r in rows))

    def test_overlap_warning_and_partial_week(self):
        overlapping = MEETINGS + [{'day': 'จันทร์', 'start_time': '11:00', 'end_time': '13:00', 'details': ''}]
        short = week(1)
        short['ends_on'] = (MON + timedelta(days=1)).isoformat()  # Thursday not in this week
        rows, warnings, _ = self.run_plan(payload([short]), meetings=overlapping)
        self.assertEqual({r['slot_key'] for r in rows}, {'mon-0900-1200', 'mon-1100-1300'})
        self.assertTrue(any('overlap' in w for w in warnings))

    def test_teaching_week_longer_than_seven_days_is_rejected(self):
        long = week(1)
        long['ends_on'] = (MON + timedelta(days=9)).isoformat()
        data = payload([long])
        self.assertTrue(any('at most 7 days' in i for i in p.issues(data)))
        rows, _, errors = self.run_plan(data)
        self.assertEqual(rows, [])
        self.assertTrue(errors)
        exam = week(1, 'final', False)
        exam['ends_on'] = (MON + timedelta(days=13)).isoformat()
        data = payload([exam])
        data.terms[0].ends_on = MON + timedelta(days=13)
        self.assertEqual(p.issues(data), [])

    def test_official_week_ranges_filter_by_original_week_including_makeups(self):
        weeks = [week(n) for n in range(1, 5)]
        closures = [{'affected_on': (MON + timedelta(weeks=2)).isoformat(),
                     'makeup_on': (MON + timedelta(weeks=2, days=5)).isoformat(), 'note': 'closed'}]
        meetings = [{'day': 'จันทร์', 'start_time': '9:00', 'end_time': '12:00', 'details': '990001 (P1) 3 (3-0-6) W:(1-2) ROOM-1'},
                    {'day': 'พฤหัสบดี', 'start_time': '13:00', 'end_time': '15:00', 'details': 'W:(1, 3-4) LAB-2'}]
        rows, warnings, errors = self.run_plan(payload(weeks, closures), meetings=meetings)
        self.assertEqual(errors, [])
        self.assertEqual([(r['academic_week'], r['slot_key'][:3], r['calendar_kind']) for r in rows],
                         [(1, 'mon', 'regular'), (1, 'thu', 'regular'), (2, 'mon', 'regular'), (3, 'thu', 'regular'), (4, 'thu', 'regular')])
        # Week 3 Monday is outside W:(1-2): its closure creates neither a cancelled meeting nor a make-up.
        inside = [dict(m, details='W:(3-3)') for m in meetings[:1]]
        rows, _, _ = self.run_plan(payload(weeks, closures), meetings=inside)
        self.assertEqual([(r['academic_week'], r['calendar_kind'], r['state']) for r in rows],
                         [(3, 'regular', 'no_class'), (3, 'makeup', 'scheduled')])
        _, warnings, _ = self.run_plan(payload(weeks), meetings=[dict(meetings[0], details='W:(1-16)')])
        self.assertTrue(any('not teaching weeks' in w for w in warnings))

    def test_unrecognized_official_week_syntax_requires_review(self):
        for details in ('W:(1-16 odd)', 'W:(8-1)', 'W:()', 'W:1-16', 'W:(1-8) W:(10-16)', 'W:(0-3)', 'W:(1-99)'):
            rows, _, errors = self.run_plan(payload([week(1)]), meetings=[dict(MEETINGS[0], details=details)])
            self.assertEqual(rows, [], details)
            self.assertTrue(any('not recognized' in e for e in errors), details)
        self.assertIsNone(p.official_weeks('ROOM-1 no week statement'))

    def test_unknown_day_is_an_error_not_a_guess(self):
        _, _, errors = self.run_plan(payload([week(1)]), meetings=[{'day': 'TBA', 'start_time': '9:00', 'end_time': '10:00'}])
        self.assertTrue(errors)

    def test_deterministic_fingerprint(self):
        a, _, _ = self.run_plan(payload([week(1), week(2)]))
        b, _, _ = self.run_plan(payload([week(1), week(2)]))
        self.assertEqual(p.fingerprint(a), p.fingerprint(b))

    def test_publish_issues(self):
        bad = payload([week(2), week(1)], [{'affected_on': MON.isoformat(), 'makeup_on': MON.isoformat(), 'note': 'x'}])
        found = p.issues(bad, page_count=1)
        self.assertTrue(any('order' in i for i in found))
        self.assertTrue(any('make-up date must differ' in i for i in found))
        self.assertTrue(p.issues(p.Payload()))
        uncertain = payload([week(1)])
        uncertain.terms[0].weeks[0].uncertain = True
        self.assertTrue(any('uncertain' in i for i in p.issues(uncertain)))
        self.assertEqual(p.issues(payload([week(1), week(2)])), [])
        with self.assertRaises(Exception):
            p.Payload.model_validate({'terms': [], 'surprise': 1})


class CoursePlanningTests(unittest.TestCase):
    def dates(self):
        return p.Payload(events=[p.Event(semester=semester, program=program, kind=kind, title=kind,
            starts_on=MON + timedelta(days=offset), ends_on=MON + timedelta(days=offset))
            for semester, program, kind, offset in [(1, 'A', 'opening', 0), (1, 'A', 'final', 28),
                (1, 'B', 'opening', 7), (1, 'B', 'final', 42), (2, 'A', 'opening', 150)]])

    def test_program_and_semester_specific_suggestions_are_not_school_weeks(self):
        source = self.dates(); before = source.model_dump(mode='json')
        options = p.planning_options(source)
        self.assertEqual([(o['semester'], o['program'], o['starts_on'], o['ends_on']) for o in options], [
            (1, 'A', str(MON), str(MON + timedelta(days=27))),
            (1, 'B', str(MON + timedelta(days=7)), str(MON + timedelta(days=41))),
            (2, 'A', str(MON + timedelta(days=150)), '')])
        plan = p.CoursePlanning(program='A', starts_on=MON, ends_on=MON + timedelta(days=15))
        draft = p.course_payload(source, 1, plan)
        self.assertEqual([w.number for w in draft.terms[0].weeks], [1, 2, 3])
        self.assertEqual(draft.terms[0].weeks[-1].ends_on, plan.ends_on)
        self.assertEqual(source.model_dump(mode='json'), before)
        self.assertEqual(p.issues(draft), [])
        self.assertTrue(self.run_errors(draft, 'even_onsite'))

    def run_errors(self, draft, mode):
        return p.plan(draft, 1, MEETINGS, mode, 'fixture')[2]

    def test_syllabus_uses_selected_program_without_inventing_curriculum(self):
        from types import SimpleNamespace
        from src.route66_ext.services.course_syllabus import document
        source = self.dates()
        source.events[1].note = 'Only for the stated course group'
        revision = SimpleNamespace(number=3, payload=source.model_dump(mode='json'))
        cls = SimpleNamespace(semester=1, academic_year=2569, registry_course_code='FIX101', registry_title=None)
        planning = p.CoursePlanning(program='A', starts_on=MON, ends_on=MON + timedelta(days=7)).model_dump(mode='json')
        doc = document(cls, SimpleNamespace(name='Synthetic calendar', track='A'), revision, planning, True, 'Verified course name')
        text = p.canonical(doc)
        self.assertIn('Verified course name', text)
        self.assertIn('Only for the stated course group', text)
        self.assertIn('22/6/2569', text)
        self.assertIn('เติมข้อมูล', text)
        self.assertNotIn(' · B · ', text)  # program B dates never merged into program A
        self.assertNotIn('3/8/2569', text)
        self.assertEqual(source.terms, [])

    def test_course_dates_need_a_real_program_and_valid_period(self):
        source = self.dates()
        with self.assertRaises(ValueError):
            p.course_payload(source, 1)
        for program, start, end in [('X', MON, MON), ('A', MON, MON - timedelta(days=1)),
                                    ('A', MON, MON + timedelta(days=280))]:
            with self.assertRaises(ValueError):
                p.course_payload(source, 1, p.CoursePlanning(program=program, starts_on=start, ends_on=end))
        reviewed = payload([week(1)])
        self.assertIs(p.course_payload(reviewed, 1), reviewed)
        with self.assertRaises(ValueError):
            p.course_payload(reviewed, 1, p.CoursePlanning(program='A', starts_on=MON, ends_on=MON))


if __name__ == '__main__':
    unittest.main()
