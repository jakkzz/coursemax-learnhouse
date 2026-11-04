"""Real PostgreSQL + HTTP correction/reporting regressions; synthetic fixtures only."""
import asyncio
import csv
from datetime import datetime, timedelta, timezone
import io
from unittest.mock import AsyncMock, patch
import unittest
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import select

from src.route66_ext.db.academic_classes import AcademicClass, AcademicClassEvent, AcademicRosterEntry, SchoolStudent, TeachingAssignment
from src.route66_ext.db.class_attendance import AttendanceEvent, AttendanceScan, AttendanceSession
from src.route66_ext.routers import class_attendance as api
from src.route66_ext.tests.services.test_class_attendance import AttendanceTests


class AttendanceReportingTests(AttendanceTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.reporting_patch = patch.object(api, 'engine', self.engine)
        self.reporting_patch.start()

    async def asyncTearDown(self):
        self.reporting_patch.stop()
        await super().asyncTearDown()

    async def teacher_row(self, session_id=None, index=0):
        self.actor = 2
        response = await self.client.get(f'/api/v1/attendance/sessions/{session_id or self.session_id}')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['students'][index]

    async def decide(self, row, status, reason, request_id=None, session_id=None, **extra):
        self.actor = 2
        body = {'roster_entry_id':row['roster_entry_id'], 'status':status, 'reason':reason,
            'expected_token':row['evidence_token'], 'request_id':str(request_id or uuid4()), **extra}
        return await self.client.post(f'/api/v1/attendance/sessions/{session_id or self.session_id}/decisions', json=body)

    async def test_persisted_correction_reset_and_every_receipt_projection_match(self):
        opened = await self.open()
        self.actor = 1
        accepted = await self.scan(opened['token'])
        self.assertEqual(accepted.status_code, 200, accepted.text)
        original = accepted.json()['receipt']
        row = await self.teacher_row()
        corrected = await self.decide(row, 'excused', 'Reviewed documented attendance evidence')
        self.assertEqual(corrected.status_code, 200, corrected.text)
        self.assertFalse(corrected.json()['retried'])
        self.assertEqual(corrected.json()['projection']['effective_status'], 'excused')
        async with self.sessions() as db:
            session = await db.get(AttendanceSession, self.session_id)
            scan = (await db.exec(select(AttendanceScan))).one()
            self.assertEqual(session.version, 0)
            self.assertEqual(scan.arrived_at, datetime.fromisoformat(original['arrived_at']))
            self.assertEqual(scan.computed_status, original['computed_status'])
        self.actor = 1
        retried_scan = await self.scan(opened['token'])
        receipt = await self.client.get('/api/v1/attendance/receipts/' + original['receipt_id'])
        own = await self.client.get(f'/api/v1/attendance/sessions/{self.session_id}')
        self.assertEqual(retried_scan.json()['receipt']['effective_status'], 'excused')
        self.assertEqual(receipt.json()['effective_status'], 'excused')
        self.assertEqual(receipt.json()['computed_status'], 'present')
        self.assertEqual(receipt.json()['arrived_at'], original['arrived_at'])
        self.assertEqual(own.json()['own']['effective_status'], 'excused')
        self.assertEqual(own.json()['own']['decision']['reason'], 'Reviewed documented attendance evidence')
        reset_row = await self.teacher_row()
        reset = await self.decide(reset_row, 'reset', 'Use the original recorded arrival evidence')
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertEqual(reset.json()['projection']['effective_status'], 'present')
        self.assertEqual(reset.json()['decision']['previous_decision_id'], corrected.json()['decision']['id'])
        self.actor = 1
        restored = await self.client.get('/api/v1/attendance/receipts/' + original['receipt_id'])
        self.assertEqual(restored.json()['effective_status'], 'present')
        async with self.sessions.begin() as db:
            entry = (await db.exec(select(AcademicRosterEntry).join(SchoolStudent).where(SchoolStudent.user_id == 1))).one()
            entry.status = 'withdrawn'; db.add(entry)
        self.assertEqual((await self.client.get('/api/v1/attendance/receipts/' + original['receipt_id'])).status_code, 200)
        self.assertEqual((await self.client.get('/api/v1/attendance/classes/20/own')).status_code, 200)
        self.assertEqual((await self.scan(opened['token'])).status_code, 403)

    async def test_stale_and_concurrent_reviewers_do_not_overwrite(self):
        row = await self.teacher_row()
        first = await self.decide(row, 'absent', 'First reviewer confirmed an absence')
        self.assertEqual(first.status_code, 200, first.text)
        stale = await self.decide(row, 'late', 'Second reviewer used stale evidence')
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertEqual(stale.json()['detail']['code'], 'stale_evidence')
        fresh = await self.teacher_row()
        bodies = [
            {'roster_entry_id':fresh['roster_entry_id'], 'status':'present', 'reason':'Concurrent reviewer one correction',
             'expected_token':fresh['evidence_token'], 'request_id':str(uuid4())},
            {'roster_entry_id':fresh['roster_entry_id'], 'status':'excused', 'reason':'Concurrent reviewer two correction',
             'expected_token':fresh['evidence_token'], 'request_id':str(uuid4())},
        ]
        results = await asyncio.gather(*(self.client.post(
            f'/api/v1/attendance/sessions/{self.session_id}/decisions', json=body) for body in bodies))
        self.assertEqual(sorted(response.status_code for response in results), [200, 409], [response.text for response in results])
        async with self.sessions() as db:
            decisions = (await db.exec(select(AttendanceEvent).where(AttendanceEvent.kind == 'attendance_decided'))).all()
            self.assertEqual(len(decisions), 2)

    async def test_uuid_lost_ack_retry_and_precommit_failure_are_atomic(self):
        row = await self.teacher_row()
        request_id = uuid4()
        body = {'roster_entry_id':row['roster_entry_id'], 'status':'late', 'reason':'Lost acknowledgement correction retry',
            'expected_token':row['evidence_token'], 'request_id':str(request_id)}
        original_commit = api.commit
        async def lost_ack(db):
            await original_commit(db)
            raise HTTPException(503, 'Synthetic lost acknowledgement')
        with patch.object(api, 'commit', lost_ack):
            failed = await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/decisions', json=body)
        self.assertEqual(failed.status_code, 503, failed.text)
        retried = await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/decisions', json=body)
        self.assertEqual(retried.status_code, 200, retried.text)
        self.assertTrue(retried.json()['retried'])
        async with self.sessions() as db:
            decisions = (await db.exec(select(AttendanceEvent).where(AttendanceEvent.kind == 'attendance_decided'))).all()
            self.assertEqual(len(decisions), 1)
            self.assertEqual(decisions[0].details['expected_token'], body['expected_token'])
        changed_token = dict(body, expected_token=('0' if body['expected_token'][0] != '0' else '1') + body['expected_token'][1:])
        collision = await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/decisions', json=changed_token)
        self.assertEqual(collision.status_code, 409, collision.text)
        self.assertEqual(collision.json()['detail']['code'], 'request_id_collision')
        changed = dict(body, status='present')
        self.assertEqual((await self.client.post(
            f'/api/v1/attendance/sessions/{self.session_id}/decisions', json=changed)).status_code, 409)
        async with self.sessions() as db:
            self.assertEqual(len((await db.exec(select(AttendanceEvent).where(AttendanceEvent.kind == 'attendance_decided'))).all()), 1)
        fresh = await self.teacher_row()
        rollback_id = uuid4()
        rollback_body = {'roster_entry_id':fresh['roster_entry_id'], 'status':'excused',
            'reason':'Failure before commit must roll back', 'expected_token':fresh['evidence_token'],
            'request_id':str(rollback_id)}
        async with self.sessions() as db:
            before = len((await db.exec(select(AttendanceEvent).where(AttendanceEvent.kind == 'attendance_decided'))).all())
        with patch.object(api, 'commit', AsyncMock(side_effect=HTTPException(503, 'Synthetic precommit failure'))):
            rolled_back = await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/decisions', json=rollback_body)
        self.assertEqual(rolled_back.status_code, 503, rolled_back.text)
        async with self.sessions() as db:
            after = len((await db.exec(select(AttendanceEvent).where(AttendanceEvent.kind == 'attendance_decided'))).all())
        self.assertEqual(after, before)
        saved = await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/decisions', json=rollback_body)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertFalse(saved.json()['retried'])

    async def test_no_class_hides_but_restore_preserves_decision(self):
        row = await self.teacher_row()
        decided = await self.decide(row, 'absent', 'Retrospective absence before cancellation')
        self.assertEqual(decided.status_code, 200, decided.text)
        state = await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/state', json={
            'state':'no_class', 'expected_version':0, 'reason':'Synthetic no-class review'})
        self.assertEqual(state.status_code, 200, state.text)
        no_class = await self.teacher_row()
        self.assertEqual(no_class['effective_status'], 'no_class')
        denied = await self.decide(no_class, 'excused', 'Cannot decide a no-class session')
        self.assertEqual(denied.status_code, 409, denied.text)
        self.assertEqual(denied.json()['detail']['code'], 'no_class')
        restored = await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/state', json={
            'state':'scheduled', 'expected_version':1, 'reason':'Synthetic session restoration'})
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual((await self.teacher_row())['effective_status'], 'absent')
        future = await self.client.post('/api/v1/attendance/classes/20/sessions', json={
            'title':'Future correction denial', 'starts_at':(self.now + timedelta(days=1)).isoformat(),
            'ends_at':(self.now + timedelta(days=1, hours=1)).isoformat()})
        self.assertEqual(future.status_code, 200, future.text)
        future_row = await self.teacher_row(future.json()['id'])
        future_decision = await self.decide(future_row, 'present', 'Future attendance cannot be decided',
            session_id=future.json()['id'])
        self.assertEqual(future_decision.status_code, 409, future_decision.text)
        self.assertEqual(future_decision.json()['detail']['code'], 'future_session')

    async def test_revoked_cross_class_and_own_only_scope(self):
        self.actor = 1
        own = await self.client.get('/api/v1/attendance/classes/20/own')
        self.assertEqual(own.status_code, 200, own.text)
        self.assertNotIn('members', own.json())
        self.assertNotIn('6900000002', own.text)
        self.assertEqual((await self.client.get('/api/v1/attendance/classes/20/summary')).status_code, 403)
        self.actor = 3
        self.assertEqual((await self.client.get('/api/v1/attendance/classes/20/own')).status_code, 403)
        async with self.sessions.begin() as db:
            other_class = AcademicClass(id=21, org_id=1, course_id=10, academic_year=2569, semester=1,
                section='P2', registry_course_id='100', registry_class_id='201', registry_course_code='990001')
            db.add(other_class)
            student = SchoolStudent(user_id=3, full_name_th='Cross class fixture', faculty='', program='')
            db.add(student); await db.flush()
            entry = AcademicRosterEntry(class_id=21, student_id=student.id, source='manual', display_position=1)
            db.add(entry); await db.flush()
            cross_entry_id = entry.id
        row = await self.teacher_row()
        cross = await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/decisions', json={
            'roster_entry_id':cross_entry_id, 'status':'present', 'reason':'Cross class must be rejected',
            'expected_token':row['evidence_token'], 'request_id':str(uuid4())})
        self.assertEqual(cross.status_code, 404, cross.text)
        malformed = await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/decisions', json={
            'roster_entry_id':row['roster_entry_id'], 'status':'present', 'reason':'Valid reason text',
            'expected_token':row['evidence_token'], 'request_id':str(uuid4()), 'extra':True})
        self.assertEqual(malformed.status_code, 422, malformed.text)
        foreign = await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/decisions', json={
            'roster_entry_id':row['roster_entry_id'], 'status':'present', 'reason':'Foreign origin is rejected',
            'expected_token':row['evidence_token'], 'request_id':str(uuid4())}, headers={'Origin':'https://evil.example'})
        self.assertEqual(foreign.status_code, 403, foreign.text)
        async with self.sessions.begin() as db:
            assignment = (await db.exec(select(TeachingAssignment).where(TeachingAssignment.user_id == 2))).one()
            assignment.active = False; db.add(assignment)
        self.assertEqual((await self.client.get('/api/v1/attendance/classes/20/summary')).status_code, 403)
        self.assertEqual((await self.decide(row, 'present', 'Revoked teacher cannot correct')).status_code, 403)

    async def test_observed_membership_gaps_withdrawal_and_reactivation(self):
        async with self.sessions.begin() as db:
            entry, student = (await db.exec(select(AcademicRosterEntry, SchoolStudent).join(
                SchoolStudent, SchoolStudent.id == AcademicRosterEntry.student_id
            ).where(SchoolStudent.user_id == 1))).one()
            points = [self.now - timedelta(days=50), self.now - timedelta(days=40),
                self.now - timedelta(days=35), self.now - timedelta(days=30),
                self.now - timedelta(days=20), self.now - timedelta(days=10)]
            db.add(AcademicClassEvent(class_id=20, student_id=student.id, actor_user_id=2,
                kind='registry_member_added', details={}, created_at=self.now - timedelta(days=45)))
            db.add(AcademicClassEvent(class_id=20, student_id=student.id, actor_user_id=2,
                kind='registry_member_missing', details={'status':'withdrawn', 'missing_count':2},
                created_at=self.now - timedelta(days=35)))
            db.add(AcademicClassEvent(class_id=20, student_id=student.id, actor_user_id=2,
                kind='registry_member_reactivated', details={}, created_at=self.now - timedelta(days=25)))
            db.add(AcademicClassEvent(class_id=20, student_id=student.id, actor_user_id=2,
                kind='manual_membership_changed', details={'entry_id':entry.id, 'status':'withdrawn', 'reason':'Synthetic'},
                created_at=self.now - timedelta(days=15)))
            entry.status = 'withdrawn'; entry.source = 'manual'; db.add(entry)
            for index, starts_at in enumerate(points):
                session = AttendanceSession(class_id=20, title=f'Historical {index}', starts_at=starts_at,
                    ends_at=starts_at + timedelta(hours=1), created_by=2)
                db.add(session); await db.flush()
                db.add(AttendanceEvent(session_id=session.id, actor_user_id=2, kind='checkin_opened', details={},
                    created_at=starts_at))
        self.actor = 1
        own = await self.client.get('/api/v1/attendance/classes/20/own')
        self.assertEqual(own.status_code, 200, own.text)
        payload = own.json()
        self.assertEqual(payload['summary']['total_sessions'], 3)
        self.assertEqual(payload['summary']['absent'], 3)
        self.assertEqual(payload['coverage']['unknown_membership'], 1)
        self.assertEqual(payload['coverage']['not_eligible'], 2)
        self.assertEqual(payload['risk'], 'unknown')
        states = {row['session']['title']:row['membership_at_session'] for row in payload['history']}
        self.assertEqual(states['Historical 0'], 'unknown')
        self.assertEqual(states['Historical 2'], 'active')  # Withdrawal is inclusive at session start.
        self.assertEqual(states['Historical 3'], 'withdrawn')
        self.assertEqual(states['Historical 4'], 'active')
        self.assertEqual(states['Historical 5'], 'withdrawn')

    async def test_personal_retrospective_decision_does_not_collect_whole_class(self):
        starts_at = self.now - timedelta(days=2)
        async with self.sessions.begin() as db:
            session = AttendanceSession(class_id=20, title='Uncollected retrospective', starts_at=starts_at,
                ends_at=starts_at + timedelta(hours=1), created_by=2)
            db.add(session); await db.flush(); session_id = session.id
        row = await self.teacher_row(session_id)
        decided = await self.decide(row, 'present', 'Teacher reviewed this individual record', session_id=session_id)
        self.assertEqual(decided.status_code, 200, decided.text)
        summary = await self.client.get('/api/v1/attendance/classes/20/summary')
        self.assertEqual(summary.status_code, 200, summary.text)
        members = {row['student_number']:row for row in summary.json()['members']}
        self.assertEqual(members['6900000001']['summary']['present'], 1)
        self.assertEqual(members['6900000001']['summary']['total_sessions'], 1)
        self.assertEqual(members['6900000002']['summary']['total_sessions'], 0)
        self.assertEqual(members['6900000002']['summary']['absent'], 0)
        self.assertGreaterEqual(members['6900000002']['coverage']['unknown_membership'], 1)
        history = await self.client.get('/api/v1/attendance/classes/20/history', params={
            'roster_entry_id':row['roster_entry_id']})
        reviewed = next(item for item in history.json()['history'] if item['session']['id'] == session_id)
        self.assertFalse(reviewed['collected'])
        self.assertEqual(reviewed['effective_status'], 'present')
        reset_row = await self.teacher_row(session_id)
        reset = await self.decide(reset_row, 'reset', 'Return this pair to recorded evidence', session_id=session_id)
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertEqual(reset.json()['projection']['effective_status'], 'unknown')
        after_reset = await self.client.get('/api/v1/attendance/classes/20/summary')
        first_after = next(item for item in after_reset.json()['members'] if item['student_number'] == '6900000001')
        self.assertEqual(first_after['summary']['total_sessions'], 0)
        self.assertEqual(first_after['summary']['absent'], 0)
        self.assertGreaterEqual(first_after['coverage']['unknown_membership'], 1)

    async def test_report_as_of_is_bound_to_the_repeatable_read_snapshot(self):
        starts_at = self.now - timedelta(days=2)
        async with self.sessions.begin() as db:
            entry = (await db.exec(select(AcademicRosterEntry).join(SchoolStudent).where(
                SchoolStudent.user_id == 1))).one()
            session = AttendanceSession(class_id=20, title='Snapshot boundary', starts_at=starts_at,
                ends_at=starts_at + timedelta(hours=1), created_by=2)
            db.add(session); await db.flush()
            session_id, entry_id = session.id, entry.id
        started, release = asyncio.Event(), asyncio.Event()
        original_load = api.reporting.load_class_data
        async def paused_load(db, cls):
            started.set()
            await release.wait()
            return await original_load(db, cls)
        self.actor = 2
        with patch.object(api.reporting, 'load_class_data', paused_load):
            request = asyncio.create_task(self.client.get('/api/v1/attendance/classes/20/summary'))
            await asyncio.wait_for(started.wait(), 2)
            await asyncio.sleep(0.001)
            decided_at = datetime.now(timezone.utc)
            async with self.sessions.begin() as db:
                db.add(AttendanceEvent(session_id=session_id, actor_user_id=2, kind='attendance_decided',
                    details={'roster_entry_id':entry_id, 'status':'present', 'reason':'Committed after report snapshot',
                        'expected_token':'a' * 64, 'request_id':str(uuid4()), 'previous_decision_id':None},
                    created_at=decided_at))
            release.set()
            snapshot = await request
        self.assertEqual(snapshot.status_code, 200, snapshot.text)
        member = next(row for row in snapshot.json()['members'] if row['roster_entry_id'] == entry_id)
        self.assertEqual(member['summary']['present'], 0)
        self.assertLess(datetime.fromisoformat(snapshot.json()['as_of']), decided_at)
        current = await self.client.get('/api/v1/attendance/classes/20/summary')
        member = next(row for row in current.json()['members'] if row['roster_entry_id'] == entry_id)
        self.assertEqual(member['summary']['present'], 1)

    async def test_summary_csv_unicode_formula_equality_keyset_and_more_than_200_sessions(self):
        base = self.now - timedelta(days=210)
        async with self.sessions.begin() as db:
            pairs = (await db.exec(select(AcademicRosterEntry, SchoolStudent).join(
                SchoolStudent, SchoolStudent.id == AcademicRosterEntry.student_id
            ).where(AcademicRosterEntry.class_id == 20).order_by(AcademicRosterEntry.id))).all()
            pairs[0][1].full_name_th = '\t=สูตร,ทดสอบ'; db.add(pairs[0][1])
            for entry, student in pairs:
                db.add(AcademicClassEvent(class_id=20, student_id=student.id, actor_user_id=2,
                    kind='registry_member_seen', details={}, created_at=base - timedelta(days=1)))
            first_session = None
            for index in range(205):
                starts_at = base + timedelta(days=index)
                session = AttendanceSession(class_id=20, title=f'Bulk {index:03d}', starts_at=starts_at,
                    ends_at=starts_at + timedelta(hours=1), created_by=2)
                db.add(session); await db.flush()
                first_session = first_session or session
                db.add(AttendanceEvent(session_id=session.id, actor_user_id=2, kind='checkin_opened', details={}))
            db.add(AttendanceEvent(session_id=first_session.id, actor_user_id=2, kind='attendance_decided', details={
                'roster_entry_id':pairs[0][0].id, 'status':'present', 'reason':'PRIVATE =formula reason',
                'request_id':str(uuid4()), 'previous_decision_id':None}))
            first_entry_id = pairs[0][0].id
        summary = await self.client.get('/api/v1/attendance/classes/20/summary')
        self.assertEqual(summary.status_code, 200, summary.text)
        first = next(row for row in summary.json()['members'] if row['roster_entry_id'] == first_entry_id)
        self.assertEqual(first['summary']['total_sessions'], 205)
        self.assertEqual(first['summary']['present'], 1)
        self.assertEqual(first['summary']['absent'], 204)
        history = await self.client.get('/api/v1/attendance/classes/20/history', params={'roster_entry_id':first_entry_id})
        self.assertEqual(len(history.json()['history']), 50)
        self.assertTrue(history.json()['next_before'])
        second_page = await self.client.get('/api/v1/attendance/classes/20/history', params={
            'roster_entry_id':first_entry_id, 'before':history.json()['next_before']})
        first_ids = {row['session']['id'] for row in history.json()['history']}
        second_ids = {row['session']['id'] for row in second_page.json()['history']}
        self.assertFalse(first_ids & second_ids)
        exported = await self.client.get('/api/v1/attendance/classes/20/summary.csv')
        self.assertEqual(exported.status_code, 200, exported.text)
        self.assertTrue(exported.content.startswith(b'\xef\xbb\xbf'))
        self.assertNotIn(b'\n', exported.content.replace(b'\r\n', b''))
        decoded = exported.content.decode('utf-8-sig')
        self.assertIn('สูตร', decoded)
        self.assertNotIn('PRIVATE', decoded)
        rows = list(csv.DictReader(io.StringIO(decoded, newline='')))
        csv_row = next(row for row in rows if row['Student number'] == first['student_number'])
        self.assertEqual(csv_row['Name'], "'\t=สูตร,ทดสอบ")
        self.assertEqual(int(csv_row['Known denominator']), first['summary']['total_sessions'])
        self.assertEqual(int(csv_row['Present']), first['summary']['present'])
        self.assertEqual(int(csv_row['Absent']), first['summary']['absent'])
        self.assertEqual(csv_row['Percentage'], f"{first['summary']['percent']:.2f}")
        self.assertEqual(csv_row['Coverage'], first['coverage']['status'])
        self.assertEqual(csv_row['Risk'], first['risk'])


    async def test_thousand_member_summary_and_csv_use_bounded_queries(self):
        from sqlalchemy import event
        base = self.now - timedelta(days=3)
        async with self.sessions.begin() as db:
            students = [SchoolStudent(student_number=str(6800000000 + index),
                full_name_th=f'Synthetic scale {index}', faculty='Fixture', program='Fixture')
                for index in range(1, 999)]
            db.add_all(students); await db.flush()
            db.add_all([AcademicRosterEntry(class_id=20, student_id=student.id,
                display_position=index + 2) for index, student in enumerate(students)])
            await db.flush()
            entries = (await db.exec(select(AcademicRosterEntry).where(AcademicRosterEntry.class_id == 20))).all()
            self.assertEqual(len(entries), 1000)
            db.add_all([AcademicClassEvent(class_id=20, student_id=entry.student_id, actor_user_id=2,
                kind='registry_member_seen', details={}, created_at=base) for entry in entries])
            session = AttendanceSession(class_id=20, title='Scale coverage', starts_at=base + timedelta(days=1),
                ends_at=base + timedelta(days=1, hours=1), created_by=2)
            db.add(session); await db.flush()
            db.add(AttendanceEvent(session_id=session.id, actor_user_id=2, kind='checkin_opened', details={}))
        statements = []
        def count(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        self.actor = 2
        event.listen(self.engine.sync_engine, 'before_cursor_execute', count)
        try:
            response = await self.client.get('/api/v1/attendance/classes/20/summary')
            self.assertEqual(response.status_code, 200, response.text[:1000])
            self.assertEqual(len(response.json()['members']), 1000)
            self.assertTrue(all(row['summary']['total_sessions'] == 1 for row in response.json()['members']))
            self.assertLess(len(statements), 30, 'No per-member SQL query loop')
            statements.clear()
            exported = await self.client.get('/api/v1/attendance/classes/20/summary.csv')
            self.assertEqual(exported.status_code, 200)
            self.assertEqual(len(list(csv.DictReader(io.StringIO(exported.content.decode('utf-8-sig'))))), 1000)
            self.assertLess(len(statements), 30)
        finally:
            event.remove(self.engine.sync_engine, 'before_cursor_execute', count)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(AttendanceReportingTests(name) for name in AttendanceReportingTests.__dict__ if name.startswith('test_'))
