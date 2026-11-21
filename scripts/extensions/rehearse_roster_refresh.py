#!/usr/bin/env python3
"""Offline specification rehearsal, NOT a worker or database implementation.

The timing/lease/UX model below is deliberately synthetic. HTML parsing executes
selected unmodified checked-in functions; the existing writer is tested separately
against disposable PostgreSQL. No network, database, app startup or runtime import.
"""
import ast
import asyncio
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
from dataclasses import dataclass, field
from html.parser import HTMLParser
from importlib.util import find_spec
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / 'apps/api/src/route66_ext/services/academic_rosters.py'
INTERVAL = 6 * 3600
COOLDOWN = 30 * 60
LEASE = 120


def current_parser():
    tree = ast.parse(SERVICE.read_text())
    names = {'_positive_number', 'source', 'Rows', 'parse_roster'}
    selected = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    namespace = {'re': re, 'HTMLParser': HTMLParser, 'urlencode': urlencode,
                 'ROSTER_URL': 'https://reg.nrru.ac.th/registrar/student_inclass_all.asp',
                 'COURSE_ROSTER_URL': 'https://reg.nrru.ac.th/registrar/teach_stdlistRTFallgroup.asp',
                 'LEGACY_MAX_BYTES': 512 * 1024, 'RTF_MAX_BYTES': 2 * 1024 * 1024}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SERVICE), 'exec'), namespace)
    return namespace


@dataclass
class Member:
    id: int
    source: str = 'registry'
    status: str = 'active'
    missing: int = 0


@dataclass(frozen=True)
class Claim:
    token: str
    version: int
    source: tuple
    deadline: int
    control_version: int


@dataclass
class Model:
    members: dict = field(default_factory=dict)
    source: tuple = ('990001', 2569, 1, 'P1', None)
    version: int = 0
    control_version: int = 0
    accepted: bool = True
    authorised: bool = True
    paused: bool = False
    next_due: int = 0
    lease: Claim | None = None
    last_hash: str | None = None
    last_applied: int | None = None
    last_attempt: int | None = None
    status: str = 'ready'
    access_status: str = 'ready'
    approved_drop: tuple | None = None
    results: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    next_id: int = 1

    def claim(self, token, now, *, force=False):
        if not self.accepted or not self.authorised or self.paused:
            return None
        if self.lease and self.lease.deadline > now:
            return None
        if now < self.next_due and not force:
            return None
        self.lease = Claim(token, self.version, self.source, now + LEASE, self.control_version)
        self.status = 'checking'
        return self.lease

    def finish(self, claim, now, numbers, digest, *, error=False,
               bridge_failed=False, reviewed_digest=None, human_actor=None):
        if claim.token in self.results:
            return self.results[claim.token]
        if self.lease != claim or claim.deadline <= now:
            return 'superseded'
        self.last_attempt = now
        if (not self.authorised or self.paused or self.source != claim.source or self.version != claim.version
                or self.control_version != claim.control_version):
            return self.terminal(claim, now, 'stale', delay=60)
        if error or not numbers or len(numbers) != len(set(numbers)) or len(numbers) > 1000:
            return self.terminal(claim, now, 'source_failed')
        if self.last_hash == digest and self.last_applied is not None and now - self.last_applied < COOLDOWN:
            return self.terminal(claim, now, 'recently_applied', delay=max(0, self.last_applied + INTERVAL - now))
        active = sum(m.source == 'registry' and m.status == 'active' for m in self.members.values())
        large_drop = active >= 10 and len(numbers) < active / 2
        human_approval = reviewed_digest == digest and human_actor is not None
        confirming_approved_drop = self.approved_drop == (digest, self.version, self.source)
        if large_drop and not (human_approval or confirming_approved_drop):
            return self.terminal(claim, now, 'needs_review')
        # Synthetic projection of existing writer semantics, not production code.
        for number in numbers:
            if number not in self.members:
                self.members[number] = Member(self.next_id)
                self.next_id += 1
            row = self.members[number]
            if row.source != 'manual':
                row.status, row.missing = 'active', 0
        for number, row in self.members.items():
            if number not in numbers and row.source == 'registry' and row.status == 'active':
                row.missing += 1
                if row.missing >= 2:
                    row.status = 'withdrawn'
        self.version += 1
        self.approved_drop = (digest, self.version, self.source) if large_drop and human_approval else None
        self.last_hash, self.last_applied = digest, now
        self.events.append({'actor_user_id': human_actor, 'origin': 'manual' if human_actor is not None else 'scheduled', 'run_id': claim.token})
        self.access_status = 'needs_repair' if bridge_failed else 'ready'
        return self.terminal(claim, now, 'applied')

    def terminal(self, claim, now, status, *, delay=INTERVAL):
        self.status, self.next_due, self.lease = status, now + delay, None
        self.results[claim.token] = status
        return status

    def run(self, token, now, numbers, digest, **options):
        claim = self.claim(token, now, force=True)
        assert claim is not None
        return self.finish(claim, now, numbers, digest, **options)


COPY = {
    'en': {'check': 'Check now', 'review': 'Review roster changes', 'retry': 'Try again',
           'resume': 'Resume automatic refresh', 'repair': 'Review course access',
           'failure': 'Could not check the registrar. Your saved roster is unchanged.',
           'initial': 'Review initial roster', 'queued': 'Check queued', 'checking': 'Checking registrar…'},
    'th': {'check': 'ตรวจสอบรายชื่อตอนนี้', 'review': 'ตรวจสอบการเปลี่ยนแปลงรายชื่อ', 'retry': 'ลองอีกครั้ง',
           'resume': 'อัปเดตรายชื่ออัตโนมัติต่อ', 'repair': 'ตรวจสอบสิทธิ์เข้าถึงรายวิชา',
           'failure': 'ตรวจสอบรายชื่อจากทะเบียนไม่ได้ รายชื่อที่บันทึกไว้ยังคงเดิม',
           'initial': 'ตรวจสอบรายชื่อครั้งแรก', 'queued': 'รอตรวจสอบรายชื่อ', 'checking': 'กำลังตรวจสอบรายชื่อจากทะเบียน…'},
}


def presentation(state, *, role='teacher', surface='saved', language='en'):
    # State/interaction contract only: not DOM, visual, responsive or a11y proof.
    if role == 'student':
        return {'roster_rows': False, 'action': None, 'details': 'own_membership_only'}
    if surface == 'official':
        return {'roster_rows': True, 'action': 'read_source', 'details': 'not_saved_membership'}
    if not state.authorised:
        return {'roster_rows': False, 'action': None, 'details': 'permission_changed'}
    key = ('initial' if not state.accepted else 'resume' if state.paused else
           state.status if state.status in ('queued', 'checking') else 'review' if state.status == 'needs_review' else
           'retry' if state.status == 'source_failed' else 'repair' if state.access_status == 'needs_repair' else 'check')
    return {'roster_rows': True, 'action': COPY[language][key], 'details': state.status,
            'disabled': key in ('queued', 'checking')}


@dataclass
class Form:
    query: str = 'Example'
    reason: str = 'Keep my explicit decision'
    selected_id: int = 7
    focus: str = 'reason'
    preview_version: int = 0
    confirmed: bool = True
    stale: bool = False

    def receive_status(self, version):
        if version != self.preview_version:
            self.stale, self.confirmed = True, False


class PlanTests(unittest.TestCase):
    def initial(self, numbers=('one', 'two')):
        state = Model()
        state.run('initial', 0, numbers, 'first')
        return state

    def test_initial_changed_hash_shortcut_breaks_two_snapshot_rule(self):
        state = self.initial()
        state.run('missing-first', INTERVAL, ['one'], 'same-source')
        if state.last_hash != 'same-source':  # proposed shortcut: wrongly skipped
            state.run('missing-second', 2 * INTERVAL, ['one'], 'same-source')
        self.assertEqual(state.members['two'].missing, 1)
        self.assertEqual(state.members['two'].status, 'active')

    def test_revised_fresh_identical_snapshot_confirms_withdrawal(self):
        state = self.initial()
        identifier = state.members['two'].id
        state.run('missing-first', INTERVAL, ['one'], 'same-source')
        state.run('missing-second', 2 * INTERVAL, ['one'], 'same-source')
        self.assertEqual((state.members['two'].id, state.members['two'].status), (identifier, 'withdrawn'))
        state.run('returned', 3 * INTERVAL, ['one', 'two'], 'returned')
        self.assertEqual((state.members['two'].id, state.members['two'].missing), (identifier, 0))

    def test_retry_within_cooldown_does_not_count_another_absence(self):
        state = self.initial()
        state.run('first', INTERVAL, ['one'], 'missing')
        result = state.run('retry', INTERVAL + 10, ['one'], 'missing')
        self.assertEqual(result, 'recently_applied')
        self.assertEqual(state.members['two'].missing, 1)
        self.assertEqual(state.next_due, 2 * INTERVAL)

    def test_clock_at_cooldown_boundary_accepts_fresh_snapshot(self):
        state = self.initial()
        state.run('first', INTERVAL, ['one'], 'missing')
        self.assertEqual(state.run('second', INTERVAL + COOLDOWN, ['one'], 'missing'), 'applied')

    def test_commit_then_lost_ack_is_idempotent(self):
        state = self.initial()
        claim = state.claim('once', INTERVAL)
        first = state.finish(claim, INTERVAL + 1, ['one'], 'missing')
        before = deepcopy(state)
        self.assertEqual(state.finish(claim, INTERVAL + 2, ['one'], 'missing'), first)
        self.assertEqual(state, before)

    def test_two_instances_share_one_claim(self):
        state = self.initial()
        self.assertIsNotNone(state.claim('first', INTERVAL))
        self.assertIsNone(state.claim('second', INTERVAL))

    def test_expired_worker_cannot_commit_over_replacement(self):
        state = self.initial()
        old = state.claim('old', INTERVAL)
        new = state.claim('new', INTERVAL + LEASE)
        self.assertEqual(state.finish(old, INTERVAL + LEASE + 1, ['one'], 'old'), 'superseded')
        self.assertEqual(state.finish(new, INTERVAL + LEASE + 2, ['one', 'two'], 'new'), 'applied')

    def test_crash_before_apply_preserves_members(self):
        state = self.initial()
        before = deepcopy(state.members)
        state.claim('crashed', INTERVAL)
        self.assertIsNotNone(state.claim('retry', INTERVAL + LEASE))
        self.assertEqual(state.members, before)

    def test_manual_edit_or_source_change_during_fetch_discards_result(self):
        for change in ('version', 'source'):
            with self.subTest(change=change):
                state = self.initial()
                claim = state.claim('stale', INTERVAL)
                if change == 'version': state.version += 1
                else: state.source = ('990001', 2569, 1, 'P2', None)
                before = deepcopy(state.members)
                self.assertEqual(state.finish(claim, INTERVAL + 1, ['one'], 'new'), 'stale')
                self.assertEqual(state.members, before)

    def test_pause_or_revocation_during_fetch_prevents_apply(self):
        for change in ('paused', 'authorised', 'pause_then_resume'):
            with self.subTest(change=change):
                state = self.initial()
                claim = state.claim('blocked', INTERVAL)
                if change == 'pause_then_resume': state.control_version += 2
                else: setattr(state, change, change == 'paused')
                before = deepcopy(state.members)
                self.assertEqual(state.finish(claim, INTERVAL + 1, ['one'], 'new'), 'stale')
                self.assertEqual(state.members, before)

    def test_unsaved_source_only_and_paused_classes_are_not_scheduled(self):
        for options in ({'accepted': False}, {'paused': True}, {'authorised': False}):
            with self.subTest(options=options): self.assertIsNone(Model(**options).claim('no', 0))

    def test_manual_active_and_withdrawn_decisions_are_preserved(self):
        state = self.initial()
        state.members['one'].source = 'manual'
        state.members['two'].source, state.members['two'].status = 'manual', 'withdrawn'
        before = deepcopy(state.members)
        state.run('present', INTERVAL, ['one', 'two'], 'present')
        state.run('absent', 2 * INTERVAL, ['three'], 'absent')
        self.assertEqual({k: state.members[k] for k in before}, before)

    def test_failure_empty_duplicate_and_oversized_never_change_roster(self):
        for rows, error in [(['one'], True), ([], False), (['one', 'one'], False), (list(map(str, range(1001))), False)]:
            with self.subTest(size=len(rows), error=error):
                state = self.initial()
                before, version, applied = deepcopy(state.members), state.version, state.last_applied
                self.assertEqual(state.run('bad', INTERVAL, rows, 'bad', error=error), 'source_failed')
                self.assertEqual((state.members, state.version, state.last_applied), (before, version, applied))
                self.assertGreater(state.last_attempt, applied)

    def test_source_outage_between_valid_missing_snapshots_is_not_a_snapshot(self):
        state = self.initial()
        state.run('missing', INTERVAL, ['one'], 'one')
        state.run('failed', 2 * INTERVAL, [], 'bad')
        self.assertEqual(state.members['two'].missing, 1)
        state.run('next-success', 3 * INTERVAL, ['one'], 'one')
        self.assertEqual(state.members['two'].status, 'withdrawn')

    def test_legacy_large_drop_boundary_excludes_manual_members(self):
        for count, incoming, expected in [(20, 9, 'needs_review'), (20, 10, 'applied'), (9, 1, 'applied')]:
            with self.subTest(count=count, incoming=incoming):
                state = self.initial(tuple(map(str, range(count))))
                state.members['manual'] = Member(100, source='manual')
                self.assertEqual(state.run('drop', INTERVAL, list(map(str, range(incoming))), 'drop'), expected)
                if expected == 'needs_review': self.assertTrue(all(m.missing == 0 for m in state.members.values()))

    def test_large_drop_review_is_bound_to_fresh_digest(self):
        for confirmed, expected in [('old', 'needs_review'), ('fresh', 'applied')]:
            with self.subTest(confirmed=confirmed):
                state = self.initial(tuple(map(str, range(20))))
                result = state.run('review', INTERVAL, ['0'], 'fresh', reviewed_digest=confirmed, human_actor=2)
                self.assertEqual(result, expected)

    def test_reviewed_large_drop_does_not_trap_teacher_in_repeat_approval(self):
        state = self.initial(tuple(map(str, range(20))))
        rows = list(map(str, range(9)))
        self.assertEqual(state.run('held', INTERVAL, rows, 'drop'), 'needs_review')
        self.assertEqual(state.run('review', INTERVAL + 60, rows, 'drop', reviewed_digest='drop', human_actor=2), 'applied')
        self.assertEqual(state.members['19'].missing, 1)
        self.assertEqual(state.run('confirming-observation', 2 * INTERVAL, rows, 'drop'), 'applied')
        self.assertEqual(state.members['19'].status, 'withdrawn')

    def test_large_drop_approval_does_not_cover_changed_source_or_manual_edit(self):
        for change in ('digest', 'version', 'source'):
            with self.subTest(change=change):
                state = self.initial(tuple(map(str, range(20))))
                state.run('review', INTERVAL, ['0'], 'approved', reviewed_digest='approved', human_actor=2)
                digest = 'different' if change == 'digest' else 'approved'
                if change == 'version': state.version += 1
                if change == 'source': state.source = ('990001', 2569, 1, 'P2', None)
                self.assertEqual(state.run('later', 2 * INTERVAL, ['0'], digest), 'needs_review')
                self.assertEqual(state.members['19'].missing, 1)

    def test_native_access_failure_is_not_a_failed_roster_import(self):
        state = self.initial()
        self.assertEqual(state.run('access', INTERVAL, ['one', 'new'], 'new', bridge_failed=True), 'applied')
        self.assertEqual(state.access_status, 'needs_repair')
        self.assertIn('new', state.members)
        self.assertEqual(presentation(state)['action'], 'Review course access')

    def test_system_attribution_does_not_fabricate_teacher_action(self):
        event = self.initial().events[-1]
        self.assertEqual(event, {'actor_user_id': None, 'origin': 'scheduled', 'run_id': 'initial'})
        tree = ast.parse((ROOT / 'apps/api/src/route66_ext/db/academic_classes.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AcademicClassEvent')
        actor = next(n for n in cls.body if isinstance(n, ast.AnnAssign) and n.target.id == 'actor_user_id')
        self.assertEqual(ast.unparse(actor.annotation), 'int')  # current schema needs a migration

    def test_no_catchup_burst_after_long_downtime(self):
        state = self.initial()
        state.run('after-downtime', 30 * INTERVAL, ['one'], 'new')
        self.assertIsNone(state.claim('catchup', 30 * INTERVAL + 2))
        self.assertEqual(state.members['two'].missing, 1)

    def test_polling_invalidates_confirmation_without_erasing_draft_or_focus(self):
        form = Form()
        before = (form.query, form.reason, form.selected_id, form.focus)
        form.receive_status(1)
        self.assertEqual((form.query, form.reason, form.selected_id, form.focus), before)
        self.assertTrue(form.stale)
        self.assertFalse(form.confirmed)

    def test_teacher_actions_and_saved_rows_in_both_languages(self):
        for language in COPY:
            for status, action in [('source_failed', 'retry'), ('needs_review', 'review'), ('applied', 'check')]:
                with self.subTest(language=language, status=status):
                    view = presentation(Model(status=status), language=language)
                    self.assertEqual(view['action'], COPY[language][action])
                    self.assertTrue(view['roster_rows'])
            self.assertEqual(presentation(Model(paused=True), language=language)['action'], COPY[language]['resume'])

    def test_student_does_not_receive_classmates_or_sync_actions(self):
        for status in ('ready', 'source_failed', 'needs_review', 'access_needs_repair'):
            view = presentation(Model(status=status), role='student')
            self.assertFalse(view['roster_rows'])
            self.assertIsNone(view['action'])

    def test_official_view_never_claims_membership_saved(self):
        self.assertEqual(presentation(Model(), surface='official')['details'], 'not_saved_membership')
        self.assertEqual(presentation(Model(), surface='official')['action'], 'read_source')

    def test_lost_permission_hides_private_rows_instead_of_showing_stale_cache(self):
        self.assertFalse(presentation(Model(authorised=False))['roster_rows'])

    def test_queued_and_checking_are_not_optimistic_success(self):
        state = self.initial()
        applied, version = state.last_applied, state.version
        for language in COPY:
            state.status = 'queued'
            self.assertEqual(presentation(state, language=language)['action'], COPY[language]['queued'])
            self.assertTrue(presentation(state, language=language)['disabled'])
        state.claim('checking', INTERVAL)
        self.assertEqual(presentation(state)['details'], 'checking')
        self.assertEqual((state.last_applied, state.version), (applied, version))

    def test_initial_review_is_not_silently_activated(self):
        for language in COPY:
            self.assertEqual(presentation(Model(accepted=False), language=language)['action'], COPY[language]['initial'])

    def test_scheduler_cannot_approve_large_drop_by_echoing_its_digest(self):
        state = self.initial(tuple(map(str, range(20))))
        self.assertEqual(state.run('drop', INTERVAL, ['0'], 'same', reviewed_digest='same'), 'needs_review')

    def test_failure_in_one_class_does_not_block_another(self):
        failed, good = self.initial(), self.initial()
        failed.run('failure', INTERVAL, [], 'bad')
        self.assertEqual(good.run('good', INTERVAL, ['one', 'two', 'new'], 'new'), 'applied')

    def test_current_parser_rejects_wrong_section_empty_and_incomplete(self):
        parser = current_parser()['parse_roster']
        cls = SimpleNamespace(academic_year=2569, semester=1, section='P1', registry_course_code='990001')
        head = '<table><tr><td>990001</td><td>2569</td><td>P1</td></tr><tr><td>ลำดับ</td><td>รหัส</td><td>ชื่อ</td><td>สาขา</td><td>สถานภาพ</td></tr><tr><td>คณะตัวอย่าง</td></tr>'
        row = '<tr><td>1</td><td>6900000001</td><td>นักศึกษา ตัวอย่าง</td><td>สาขาตัวอย่าง</td><td>1</td></tr></table>'
        self.assertEqual(len(parser((head + row).encode('cp874'), cls)), 1)
        for html in [(head + row).replace('P1', 'P2'), head + '</table>', (head + row).replace('6900000001', 'bad')]:
            with self.assertRaises(ValueError): parser(html.encode('cp874'), cls)

    def test_null_class_id_uses_reviewed_rtf_not_manual_mode(self):
        source = current_parser()['source']
        cls = SimpleNamespace(registry_course_id='100', registry_class_id=None, academic_year=2569, semester=1, section='P1')
        self.assertEqual(source(cls)['kind'], 'course_rtf')
        cls.registry_class_id = '200'
        self.assertEqual(source(cls)['kind'], 'legacy_html')


@unittest.skipUnless(find_spec('fastapi'), 'Run lifecycle contracts in the existing bounded API image')
class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_public_router_lifespan_composes_native_startup_and_cancellation(self):
        from fastapi import APIRouter, FastAPI
        events = []
        started = asyncio.Event()

        async def worker():
            events.append('worker_start'); started.set()
            try: await asyncio.Event().wait()
            finally: events.append('worker_stop')

        @asynccontextmanager
        async def native(app):
            events.append('native_start')
            try: yield {'native_state': True}
            finally: events.append('native_stop')

        @asynccontextmanager
        async def owned(app):
            task = asyncio.create_task(worker())
            await started.wait()
            try: yield
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError): await task

        app = FastAPI(lifespan=native)
        app.include_router(APIRouter(lifespan=owned))
        async with app.router.lifespan_context(app) as state:
            self.assertTrue(state['native_state'])
            events.append('serve')
        self.assertEqual(events, ['native_start', 'worker_start', 'serve', 'worker_stop', 'native_stop'])

    async def test_native_startup_failure_never_starts_owned_worker(self):
        from fastapi import APIRouter, FastAPI
        events = []

        @asynccontextmanager
        async def native(app):
            raise RuntimeError('synthetic native startup failure')
            yield

        @asynccontextmanager
        async def owned(app):
            events.append('should_not_start')
            yield

        app = FastAPI(lifespan=native)
        app.include_router(APIRouter(lifespan=owned))
        with self.assertRaises(RuntimeError):
            async with app.router.lifespan_context(app): pass
        self.assertEqual(events, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
