"""HTTP + PostgreSQL proof; fictional users, no providers or live data."""
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import unittest
from fastapi import HTTPException
from sqlalchemy import event
from sqlmodel import select
from src.db.users import User
from src.route66_ext.db.academic_classes import AcademicRosterEntry, SchoolStudent
from src.route66_ext.db.class_attendance import AttendanceScan, AttendanceSession
from src.route66_ext.routers import class_attendance as api
from src.route66_ext.services import class_attendance as service
from src.route66_ext.tests.services.test_class_attendance import AttendanceTests
from src.route66_ext.tests.services.test_attendance_handoff import MemoryRedis
from src.route66_ext.services.attendance_handoff import Handoffs


class ArrivalTests(AttendanceTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.redis = MemoryRedis()
        self.store = Handoffs(self.redis, self.config.deployment)
        @asynccontextmanager
        async def resources(config): yield self.redis, None
        self.arrival_patches = [patch.object(api, 'settings', lambda:self.config), patch.object(api, 'resources', resources), patch.object(api, 'engine', self.engine)]
        for item in self.arrival_patches: item.start()

    async def asyncTearDown(self):
        for item in reversed(self.arrival_patches): item.stop()
        await super().asyncTearDown()

    async def prepare(self):
        opened = await self.open()
        result = await self.client.post('/api/v1/attendance/check-in/prepare', json={'token':opened['token']})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(set(result.json()), {'handoff', 'expires_at', 'return_path'})
        self.assertNotIn(opened['token'], result.text)
        return result.json()['handoff']

    async def finish(self, handle):
        return await self.client.post('/api/v1/attendance/check-in/complete', json={'handoff':handle})

    async def count_scans(self):
        async with self.sessions() as db: return len((await db.exec(select(AttendanceScan))).all())

    async def other_member(self):
        async with self.sessions.begin() as db:
            rows = (await db.exec(select(AcademicRosterEntry).where(AcademicRosterEntry.class_id==20).order_by(AcademicRosterEntry.id))).all()
            student = await db.get(SchoolStudent, rows[1].student_id)
            student.user_id = 3; db.add(student)

    def clock(self, at):
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None): return at if tz else at.replace(tzinfo=None)
        return patch.object(api, 'datetime', Clock)

    async def test_delayed_login_uses_reserved_arrival_and_same_receipt_after_deadline(self):
        handle = await self.prepare(); held = await self.store.get(handle)
        self.actor = 1
        with self.clock(held.arrived_at+timedelta(minutes=8)):
            result = await self.finish(handle)
        self.assertEqual(result.status_code, 200, result.text)
        receipt = result.json()['receipt']
        self.assertEqual(datetime.fromisoformat(receipt['arrived_at']), held.arrived_at)
        self.assertEqual(receipt['computed_status'], 'present')
        with self.clock(held.arrived_at+timedelta(minutes=11)):
            retry = await self.finish(handle)
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertFalse(retry.json()['created'])
        self.assertEqual(retry.json()['receipt']['receipt_id'], receipt['receipt_id'])
        self.assertEqual(await self.count_scans(), 1)

    async def test_unrelated_actor_cannot_claim_then_other_eligible_actor_cannot_reuse(self):
        handle = await self.prepare(); self.actor = 3
        self.assertEqual((await self.finish(handle)).status_code, 403)
        self.assertEqual((await self.store.get(handle)).owner, 0)
        self.actor = 1
        self.assertEqual((await self.finish(handle)).status_code, 200)
        await self.other_member(); self.actor = 3
        denied = await self.finish(handle)
        self.assertEqual(denied.status_code, 409, denied.text)
        self.assertEqual(denied.json()['detail']['code'], 'handoff_claimed')
        self.assertEqual(await self.count_scans(), 1)

    async def test_deadline_no_class_and_version_change_create_no_scan(self):
        handle = await self.prepare(); held = await self.store.get(handle); self.actor = 1
        with self.clock(held.expires_at):
            self.assertEqual((await self.finish(handle)).status_code, 410)
        self.actor = 2
        state = await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/state', json={'state':'no_class','expected_version':0,'reason':'Synthetic cancellation'})
        self.assertEqual(state.status_code, 200, state.text)
        self.actor = 1
        self.assertEqual((await self.finish(handle)).status_code, 410)
        self.actor = 2
        await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/state', json={'state':'scheduled','expected_version':1,'reason':'Synthetic restoration'})
        self.actor = 1
        self.assertEqual((await self.finish(handle)).status_code, 410)
        self.assertEqual(await self.count_scans(), 0)

    async def test_session_end_caps_handoff_and_withdrawal_is_rechecked(self):
        created = await self.client.post('/api/v1/attendance/classes/20/sessions', json={
            'title':'Synthetic short session', 'starts_at':(self.now-timedelta(minutes=5)).isoformat(),
            'ends_at':(self.now+timedelta(minutes=1)).isoformat()})
        self.assertEqual(created.status_code,200,created.text);self.session_id=created.json()['id']
        handle = await self.prepare(); held = await self.store.get(handle)
        async with self.sessions() as db: self.assertEqual(held.expires_at, (await db.get(AttendanceSession,self.session_id)).ends_at)
        self.actor = 1
        async with self.sessions.begin() as db:
            entry = (await db.exec(select(AcademicRosterEntry).join(SchoolStudent).where(SchoolStudent.user_id==1))).one()
            entry.status = 'withdrawn'; db.add(entry)
        self.assertEqual((await self.finish(handle)).status_code, 403)
        self.assertEqual((await self.store.get(handle)).owner, 0)
        self.assertEqual(await self.count_scans(), 0)

    async def test_concurrent_completion_and_lost_ack_recover_canonical_receipt(self):
        handle = await self.prepare(); self.actor = 1
        original = api.commit
        async def lost_ack(db):
            await original(db)
            raise HTTPException(503, 'Synthetic lost acknowledgement')
        with patch.object(api, 'commit', lost_ack):
            self.assertEqual((await self.finish(handle)).status_code, 503)
        results = await asyncio.gather(*(self.finish(handle) for _ in range(8)))
        self.assertTrue(all(item.status_code==200 for item in results), [item.text for item in results])
        self.assertEqual(len({item.json()['receipt']['receipt_id'] for item in results}), 1)
        self.assertTrue(all(not item.json()['created'] for item in results))
        self.assertEqual(await self.count_scans(), 1)

    async def test_failure_before_commit_rolls_back_and_retries(self):
        handle = await self.prepare(); self.actor = 1
        with patch.object(api, 'commit', AsyncMock(side_effect=HTTPException(503, 'Synthetic storage failure'))):
            self.assertEqual((await self.finish(handle)).status_code, 503)
        self.assertEqual(await self.count_scans(), 0)
        result = await self.finish(handle)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertTrue(result.json()['created'])

    async def test_prepare_needs_no_identity_but_completion_and_stream_do(self):
        opened = await self.open()
        from src.route66_ext.routers.school_identity import context as native_context
        with patch.object(api, 'context', native_context):
            prepared = await self.client.post('/api/v1/attendance/check-in/prepare', json={'token':opened['token']})
            self.assertEqual(prepared.status_code, 200, prepared.text)
            self.assertEqual((await self.finish(prepared.json()['handoff'])).status_code, 401)
            response = await self.client.get(f'/api/v1/attendance/sessions/{self.session_id}/events', headers={'X-User-Id':'2'})
            self.assertEqual(response.status_code, 401, response.text)
        for body in ({'token':opened['token'],'arrived_at':self.now.isoformat()}, {'token':'bad'}):
            self.assertEqual((await self.client.post('/api/v1/attendance/check-in/prepare',json=body)).status_code,422)
        self.assertEqual((await self.client.post('/api/v1/attendance/check-in/prepare',json={'token':opened['token']},headers={'Origin':'https://foreign.example'})).status_code,403)
        self.assertEqual(await self.count_scans(), 0)

    async def test_uncollected_past_date_is_not_an_invented_absence(self):
        created = await self.client.post('/api/v1/attendance/classes/20/sessions', json={
            'title':'Synthetic historical date', 'starts_at':(self.now-timedelta(days=2)).isoformat(),
            'ends_at':(self.now-timedelta(days=1)).isoformat()})
        self.assertEqual(created.status_code,200,created.text);self.session_id=created.json()['id']
        self.actor = 1
        result = await self.client.get(f'/api/v1/attendance/sessions/{self.session_id}')
        self.assertEqual(result.json()['own']['status'], 'unrecorded')
        self.assertEqual(result.json()['own']['receipts'], [])

    async def test_stream_pushes_committed_own_state_and_releases_connections(self):
        handle = await self.prepare(); self.actor = 1
        accepted = await self.finish(handle)
        request = SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
        connections = [0]
        def checkout(*_): connections[0] += 1
        def checkin(*_): connections[0] -= 1
        event.listen(self.engine.sync_engine, 'checkout', checkout); event.listen(self.engine.sync_engine, 'checkin', checkin)
        stream = None
        try:
            async with self.sessions() as db: first = await api.session_snapshot(request,db,self.session_id)
            stream = api.session_events(request,self.session_id,first,interval=0.01,lifetime=1)
            initial = await anext(stream)
            self.assertEqual(connections[0],0)
            self.assertNotIn('student_number',initial);self.assertNotIn('roster_entry_id',initial);self.assertNotIn('"students"',initial)
            self.actor = 2
            changed = await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/state',json={'state':'no_class','expected_version':0,'reason':'Synthetic live cancellation'})
            self.assertEqual(changed.status_code,200,changed.text);self.actor=1
            pushed = await anext(stream)
            payload = json.loads(pushed.split('data: ',1)[1])
            self.assertEqual(payload['own']['status'],'no_class')
            self.assertEqual(payload['own']['receipts'][0]['effective_status'],'no_class')
            self.assertEqual(payload['own']['receipts'][0]['computed_status'],'present')
            self.assertEqual(payload['own']['receipts'][0]['receipt_id'],accepted.json()['receipt']['receipt_id'])
            self.assertEqual(connections[0],0)
            async with self.sessions.begin() as db:
                entry=(await db.exec(select(AcademicRosterEntry).join(SchoolStudent).where(SchoolStudent.user_id==1))).one()
                entry.status='withdrawn';db.add(entry)
                from src.route66_ext.db.academic_classes import AcademicClass
                cls=await db.get(AcademicClass,20);cls.version+=1;db.add(cls)
            lost = await anext(stream)
            self.assertIn('event: access_lost',lost);self.assertNotIn('students',lost)
        finally:
            if stream: await stream.aclose()
            event.remove(self.engine.sync_engine,'checkout',checkout);event.remove(self.engine.sync_engine,'checkin',checkin)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(ArrivalTests(name) for name in ArrivalTests.__dict__ if name.startswith('test_'))
