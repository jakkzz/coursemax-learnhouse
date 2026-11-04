#!/usr/bin/env python3
"""Offline specification rehearsal, NOT application implementation.

Runs the real pure attendance policy and unmodified selected projection functions.
The journal, authorization and transaction below are in-memory models: they do not
prove PostgreSQL locking, HTTP permissions, SSE delivery or browser interactions.
No database, network, native app imports or live records are used.
"""
import ast
import csv
import io
import sys
import unittest
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/api'))
from src.route66_ext.services.attendance_policy import (  # noqa: E402
    SessionPolicy, _utc, counts_as_completed_session, missing_attendance_status,
    summarize_attendance,
)

# Exercise actual checked-in projection without importing application/DB dependencies.
SERVICE = ROOT / 'apps/api/src/route66_ext/services/class_attendance.py'
selected = [n for n in ast.parse(SERVICE.read_text()).body
            if isinstance(n, ast.FunctionDef) and n.name in {'policy', 'own_receipt', 'scan_projection'}]
assert len(selected) == 3
actual = dict(SessionPolicy=SessionPolicy, _utc=_utc, missing_attendance_status=missing_attendance_status)
exec(compile(ast.Module(body=selected, type_ignores=[]), str(SERVICE), 'exec'), actual)
START = datetime(2026, 11, 1, 2, tzinfo=timezone.utc)
NOW = START + timedelta(days=10)
STATUSES = {'present', 'late', 'absent', 'excused'}


@dataclass(frozen=True)
class Session:
    id: int = 1
    class_id: int = 20
    title: str = 'Synthetic attendance ชั้นเรียนตัวอย่าง'
    starts_at: datetime = START
    ends_at: datetime = START + timedelta(hours=2)
    timezone: str = 'Asia/Bangkok'
    state: str = 'scheduled'
    version: int = 0
    grace_minutes: int = 10
    late_threshold_minutes: int = 20


@dataclass(frozen=True)
class Scan:
    id: int = 1
    receipt_id: str = 'synthetic-receipt'
    arrived_at: datetime = START + timedelta(minutes=15)
    computed_status: str = 'late'
    kind: str = 'entry'


@dataclass(frozen=True)
class Observation:
    at: datetime
    active: bool


def eligibility(session, observations):
    """Known observation interval, never an inferred official registration date."""
    previous = [o for o in observations if o.at < session.starts_at
                or (o.active and o.at == session.starts_at)]
    return max(previous, key=lambda o: o.at).active if previous else None


@dataclass(frozen=True)
class Decision:
    id: int
    session_id: int
    roster_id: int
    actor: int
    status: str  # 'reset' returns to evidence-derived projection.
    reason: str
    request_id: str
    token: tuple


class Conflict(Exception):
    pass


class Journal:
    """Serial transaction model. Real implementation must use existing SQL lock."""
    def __init__(self):
        self.events = ()
        self.class_version = 1

    def current(self, session, roster_id):
        return next((e for e in reversed(self.events)
                     if (e.session_id, e.roster_id) == (session.id, roster_id)), None)

    def token(self, session, roster_id, scans=()):
        latest = self.current(session, roster_id)
        return (session.version, self.class_version, latest.id if latest else 0,
                tuple((s.id, s.receipt_id) for s in scans))

    def append(self, session, roster_id, *, actor=7, authorized=True, same_class=True,
               status='excused', reason='Synthetic teacher reason', request_id='synthetic-1',
               token=None, scans=(), now=NOW, fail=False):
        if not authorized or not same_class:
            raise PermissionError('Existing manager/class authority required')
        reason = reason.strip()
        if status not in STATUSES | {'reset'} or not 5 <= len(reason) <= 500:
            raise ValueError('Typed status and meaningful reason required')
        for event in self.events:
            if event.request_id == request_id:
                if (event.session_id, event.roster_id, event.actor, event.status, event.reason) == (
                        session.id, roster_id, actor, status, reason):
                    return event  # Lost acknowledgement: reuse the same immutable decision.
                raise Conflict('Retry key already records a different intent')
        if session.state != 'scheduled' or session.starts_at > now:
            raise Conflict('No-class or future session')
        if token != self.token(session, roster_id, scans):
            raise Conflict('Evidence changed; preserve draft and reload')
        event = Decision(len(self.events) + 1, session.id, roster_id, actor,
                         status, reason, request_id, token)
        if fail:
            raise RuntimeError('Synthetic failure before commit')
        self.events += (event,)
        return event


def projection(session, scans=(), *, collected=False, eligible=True, decision=None, now=NOW):
    base = actual['scan_projection'](session, scans, now, collected=collected)
    if session.state == 'no_class':
        status, basis = 'no_class', 'no_class'
    elif decision and decision.status != 'reset':
        status, basis = decision.status, 'teacher_decision'
    elif scans:
        status, basis = base['status'], 'scan'
    elif eligible is False:
        status, basis = 'not_eligible', 'observed_membership'
    elif eligible is None:
        status, basis = 'unknown', 'unknown_membership'
    else:
        status, basis = base['status'], 'collection' if collected else 'not_collected'
    counted = (counts_as_completed_session(actual['policy'](session), now=now)
               and status in STATUSES and (eligible is True or bool(scans) or basis == 'teacher_decision'))
    # Existing scans remain immutable; DTOs separately describe current effective result.
    return {**base, 'status': status, 'basis': basis, 'counted': counted,
            'completed': counts_as_completed_session(actual['policy'](session), now=now),
            'receipts': [actual['own_receipt'](s, session, status) for s in scans]}


def report(rows, *, active=True):
    included = [r['status'] for r in rows if r['counted']]
    aggregate = summarize_attendance(len(included), included)
    incomplete = sum(r['completed'] and r['status'] in {'unknown', 'unrecorded'} for r in rows)
    return {'total': aggregate.total_sessions, 'present': aggregate.present,
            'late': aggregate.late, 'absent': aggregate.absent, 'excused': aggregate.excused,
            'percent': aggregate.percent, 'unknown_or_unrecorded': incomplete,
            'at_risk': aggregate.at_risk if active and not incomplete else None}


def csv_text(value):
    value = str(value)
    return "'" + value if value.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r', '\n')) else value


def export_summary(name, number, summary):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\r\n')
    writer.writerow(['student_number', 'name', *summary.keys()])
    writer.writerow([csv_text(number), csv_text(name), *(
        '' if v is None else f'{v:.2f}' if k == 'percent' else str(v)
        for k, v in summary.items())])
    return '\ufeff' + stream.getvalue()


class RehearsalTests(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.journal = Journal()

    def decide(self, **kwargs):
        return self.journal.append(self.session, 11, token=self.journal.token(self.session, 11), **kwargs)

    def test_actual_baseline_preserves_earliest_scan_and_uncollected_gap(self):
        scans = (Scan(), Scan(id=2, arrived_at=START + timedelta(minutes=2), computed_status='present'))
        self.assertEqual(actual['scan_projection'](self.session, scans, NOW)['status'], 'present')
        self.assertEqual(actual['scan_projection'](self.session, (), NOW)['status'], 'unrecorded')
        self.assertEqual(actual['scan_projection'](self.session, (), NOW, collected=True)['status'], 'absent')

    def test_correction_does_not_rewrite_original_receipt(self):
        scan = Scan()
        token = self.journal.token(self.session, 11, (scan,))
        decision = self.journal.append(self.session, 11, scans=(scan,), token=token)
        row = projection(self.session, (scan,), decision=decision)
        self.assertEqual((row['status'], row['receipts'][0]['computed_status'], scan.computed_status), ('excused', 'late', 'late'))
        self.assertEqual(row['receipts'][0]['effective_status'], 'excused')

    def test_later_scan_cannot_replace_teacher_decision(self):
        d = self.decide(status='absent')
        self.assertEqual(projection(self.session, (Scan(computed_status='present'),), decision=d)['status'], 'absent')

    def test_reset_appends_and_returns_to_scan_or_unknown(self):
        self.decide()
        reset = self.decide(status='reset', request_id='reset-1')
        self.assertEqual(len(self.journal.events), 2)
        self.assertEqual(projection(self.session, (Scan(),), decision=reset)['status'], 'late')
        self.assertFalse(projection(self.session, (), decision=reset, collected=False)['counted'])

    def test_no_class_hides_decision_restore_recovers_it(self):
        d = self.decide()
        cancelled = replace(self.session, state='no_class', version=1)
        self.assertEqual(projection(cancelled, (Scan(),), decision=d)['status'], 'no_class')
        self.assertFalse(projection(cancelled, (Scan(),), decision=d)['counted'])
        self.assertEqual(projection(replace(cancelled, state='scheduled', version=2), decision=d)['status'], 'excused')
        self.assertEqual(len(self.journal.events), 1)

    def test_personal_retrospective_decision_does_not_collect_whole_class(self):
        d = self.decide()
        self.assertTrue(projection(self.session, decision=d)['counted'])
        other = projection(self.session, collected=False)
        self.assertEqual(other['status'], 'unrecorded')
        self.assertFalse(other['counted'])

    def test_only_known_collected_completed_pairs_count(self):
        rows = [projection(self.session, collected=True),
                projection(self.session, collected=False),
                projection(self.session, collected=True, eligible=None),
                projection(self.session, collected=True, eligible=False),
                projection(replace(self.session, state='no_class'), collected=True),
                projection(replace(self.session, starts_at=NOW+timedelta(days=1), ends_at=NOW+timedelta(days=2)), collected=True)]
        self.assertEqual(report(rows)['total'], 1)
        self.assertEqual(report(rows)['absent'], 1)
        self.assertIsNone(report(rows)['at_risk'])

    def test_join_withdraw_reactivate_never_backdate(self):
        observations = [Observation(START-timedelta(days=2), True),
                        Observation(START+timedelta(days=1), False),
                        Observation(START+timedelta(days=4), True)]
        for days, expected in [(-3, None), (0, True), (2, False), (5, True)]:
            self.assertIs(eligibility(replace(self.session, starts_at=START+timedelta(days=days)), observations), expected)
        # Importing today's roster is not proof about an earlier session.
        self.assertIsNone(eligibility(self.session, [Observation(NOW, True)]))
        # Preserve the existing inclusive withdrawal boundary, not current status.
        self.assertTrue(eligibility(self.session, [Observation(START-timedelta(days=1), True), Observation(START, False)]))

    def test_pair_evidence_survives_current_withdrawal_and_missing_history(self):
        row = projection(self.session, (Scan(),), eligible=None)
        self.assertTrue(row['counted'])
        self.assertEqual(report([row], active=False)['late'], 1)
        self.assertIsNone(report([row], active=False)['at_risk'])

    def test_same_retry_one_event_changed_intent_conflicts(self):
        token = self.journal.token(self.session, 11)
        first = self.journal.append(self.session, 11, token=token)
        self.assertIs(self.journal.append(self.session, 11, token=token), first)
        with self.assertRaises(Conflict):
            self.journal.append(self.session, 11, token=token, status='absent')
        self.assertEqual(len(self.journal.events), 1)

    def test_two_serialized_reviewers_only_one_wins_stale_token(self):
        token = self.journal.token(self.session, 11)
        self.journal.append(self.session, 11, token=token)
        with self.assertRaises(Conflict):
            self.journal.append(self.session, 11, actor=8, request_id='other', token=token)
        self.assertEqual(len(self.journal.events), 1)

    def test_roster_state_or_scan_change_requires_new_review(self):
        token = self.journal.token(self.session, 11)
        self.journal.class_version += 1
        with self.assertRaises(Conflict):
            self.journal.append(self.session, 11, token=token)
        token = self.journal.token(self.session, 11)
        with self.assertRaises(Conflict):
            self.journal.append(replace(self.session, version=1), 11, token=token)
        with self.assertRaises(Conflict):
            self.journal.append(self.session, 11, scans=(Scan(),), token=token)
        self.assertEqual(self.journal.events, ())

    def test_authority_rechecked_even_for_committed_retry(self):
        self.decide()
        with self.assertRaises(PermissionError):
            self.decide(authorized=False)
        with self.assertRaises(PermissionError):
            self.decide(same_class=False)
        self.assertEqual(len(self.journal.events), 1)

    def test_validation_no_future_or_no_class_decision(self):
        for kwargs in ({'status':'unknown'}, {'reason':'   '}, {'reason':'x'*501}):
            with self.assertRaises(ValueError):
                self.decide(**kwargs)
        for session in (replace(self.session, state='no_class'), replace(self.session, starts_at=NOW+timedelta(days=1))):
            with self.assertRaises(Conflict):
                self.journal.append(session, 11, token=self.journal.token(session, 11))
        self.assertEqual(self.journal.events, ())

    def test_explicit_retrospective_decision_establishes_only_reviewed_pair(self):
        decision = self.decide(reason='Teacher reviewed this saved member for this session')
        reviewed = projection(self.session, eligible=None, decision=decision)
        untouched = projection(self.session, eligible=None)
        self.assertTrue(reviewed['counted'])
        self.assertEqual((reviewed['status'], untouched['status']), ('excused', 'unknown'))
        self.assertFalse(untouched['counted'])
        reset = self.decide(status='reset', request_id='reset-review')
        self.assertEqual(projection(self.session, eligible=None, decision=reset)['status'], 'unknown')

    def test_failed_commit_leaves_no_decision_retry_can_succeed(self):
        with self.assertRaises(RuntimeError):
            self.decide(fail=True)
        self.assertEqual(self.journal.events, ())
        self.assertEqual(self.decide().id, 1)

    def test_shared_arithmetic_empty_and_exact_risk_boundary(self):
        rows = [projection(self.session, (Scan(computed_status=s),)) for s in ['present','late']]
        rows += [projection(self.session, decision=SimpleNamespace(status='excused')),
                 projection(self.session, collected=True)]
        result = report(rows)
        self.assertEqual((result['total'],result['percent']), (4,75.0))
        self.assertTrue(result['at_risk'])
        self.assertIsNone(report([])['percent'])
        self.assertFalse(summarize_attendance(5, ['present']*4).at_risk)

    def test_csv_matches_same_summary_preserves_unicode_quotes_and_blank_percent(self):
        summary = report([projection(self.session, (Scan(),))])
        raw = export_summary('ทดสอบ, "Name"\nSecond line', '0690000001', summary)
        self.assertTrue(raw.startswith('\ufeff'))
        row = next(csv.DictReader(io.StringIO(raw.lstrip('\ufeff'))))
        self.assertEqual(row['student_number'], '0690000001')
        self.assertEqual(row['name'], 'ทดสอบ, "Name"\nSecond line')
        self.assertEqual((row['total'],row['late'],row['percent']), ('1','1','100.00'))
        empty = next(csv.DictReader(io.StringIO(export_summary('Empty','0690000001',report([])).lstrip('\ufeff'))))
        self.assertEqual(empty['percent'], '')

    def test_csv_formula_text_is_not_executable(self):
        for name in ['=1+1', '+SUM(A1)', '-1+2', '@SUM(A1)', '  =1', '\t=1', '\r=1', '\n=1']:
            row = next(csv.DictReader(io.StringIO(export_summary(name,'0690000001',report([])).lstrip('\ufeff'))))
            self.assertTrue(row['name'].startswith("'"), name)

    def test_every_existing_projection_caller_is_in_integration_inventory(self):
        service = ast.parse(SERVICE.read_text())
        router = ast.parse((ROOT/'apps/api/src/route66_ext/routers/class_attendance.py').read_text())
        callers = set()
        for tree in (service, router):
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for call in ast.walk(node):
                        if isinstance(call, ast.Call) and ((isinstance(call.func, ast.Name) and call.func.id == 'scan_projection') or
                            (isinstance(call.func, ast.Attribute) and call.func.attr == 'scan_projection')):
                            callers.add(node.name)
        self.assertEqual(callers, {'accept_scan', 'session_snapshot', 'receipt'})


if __name__ == '__main__':
    unittest.main()
