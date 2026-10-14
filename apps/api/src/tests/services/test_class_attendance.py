"""Real isolated PostgreSQL + HTTP attendance task and denial tests, synthetic only."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
from contextlib import asynccontextmanager
import unittest
import httpx
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlmodel import select
from src.tests.services.test_academic_rosters import AcademicRosterTests
from src.db.class_attendance import AttendanceSession, AttendanceScan, AttendanceChallenge, AttendanceEvent, ATTENDANCE_TABLES
from src.db.academic_classes import AcademicRosterEntry, AcademicClass, TeachingAssignment, SchoolStudent
from src.db.users import User
from src.services import class_attendance as s, academic_rosters as roster
from src.routers import class_attendance as api


class AttendanceTests(AcademicRosterTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        await self.claim()
        await self.snapshot('6900000001', '6900000002')
        self.now = datetime.now(timezone.utc)
        async with self.sessions.begin() as db:
            session = AttendanceSession(class_id=20, title='Synthetic session', starts_at=self.now-timedelta(minutes=5), ends_at=self.now+timedelta(hours=1), created_by=2)
            db.add(session)
            await db.flush()
            self.session_id = session.id
        self.actor = 2
        self.config = SimpleNamespace(org_id=1, deployment='fixture', handoff=SimpleNamespace(client=SimpleNamespace(public_origin='https://learn.example.com')))
        self.app = FastAPI()
        self.app.include_router(api.router, prefix='/api/v1/attendance')
        async def database():
            async with self.sessions() as db:
                yield db
        async def context(request, db):
            return await db.get(User, self.actor), self.config, None
        @asynccontextmanager
        async def resources(config):
            yield None, None
        self.app.dependency_overrides[api.get_db_session] = database
        self.attendance_patches = [patch.object(api,'context',context),patch.object(api,'resources',resources),patch.object(api,'throttle',AsyncMock())]
        for p in self.attendance_patches:p.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='https://learn.example.com',headers={'Origin':'https://learn.example.com'})

    async def asyncTearDown(self):
        await self.client.aclose()
        for p in reversed(self.attendance_patches):p.stop()
        await super().asyncTearDown()

    async def open(self,kind='entry'):
        response=await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/open',json={'kind':kind})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    async def scan(self,token):
        return await self.client.post('/api/v1/attendance/check-in',json={'token':token})

    async def test_teacher_create_open_student_scan_receipt_and_reload(self):
        created=await self.client.post('/api/v1/attendance/classes/20/sessions',json={'title':'Second synthetic session','starts_at':self.now.isoformat(),'ends_at':(self.now+timedelta(hours=1)).isoformat(),'timezone':'Asia/Bangkok'})
        self.assertEqual(created.status_code,200,created.text)
        self.session_id=created.json()['id']
        opened=await self.open()
        self.assertIn('/attendance/check-in#',opened['checkin_url'])
        self.actor=1
        response=await self.scan(opened['token'])
        self.assertEqual(response.status_code,200,response.text)
        receipt=response.json()['receipt']
        self.assertEqual(receipt['computed_status'],'present')
        saved=await self.client.get('/api/v1/attendance/receipts/'+receipt['receipt_id'])
        self.assertEqual(saved.json(),receipt)
        own=await self.client.get(f'/api/v1/attendance/sessions/{self.session_id}')
        self.assertNotIn('students',own.json())
        self.assertNotIn('events',own.json())
        self.assertEqual(own.json()['own']['first_arrived_at'],receipt['arrived_at'])
        self.assertIn('no-store',own.headers['cache-control'])
        self.actor=2
        view=await self.client.get(f'/api/v1/attendance/sessions/{self.session_id}')
        self.assertEqual(view.json()['students'][0]['status'],'present')

    async def test_same_challenge_retry_returns_original_receipt_even_after_expiry(self):
        opened=await self.open();self.actor=1
        first=await self.scan(opened['token']);second=await self.scan(opened['token'])
        self.assertTrue(first.json()['created']);self.assertFalse(second.json()['created'])
        self.assertEqual(first.json()['receipt'],second.json()['receipt'])
        async with self.sessions.begin() as db:
            await roster.serialize(db)
            receipt,created=await s.accept_scan(db,opened['token'],await db.get(User,1),1,self.now+timedelta(days=1))
            self.assertFalse(created);self.assertEqual(receipt['receipt_id'],first.json()['receipt']['receipt_id'])
        async with self.sessions() as db:self.assertEqual(len((await db.exec(select(AttendanceScan))).all()),1)

    async def test_concurrent_scans_have_one_receipt(self):
        opened=await self.open();self.actor=1
        results=await asyncio.gather(*(self.scan(opened['token']) for _ in range(8)))
        self.assertTrue(all(r.status_code==200 for r in results),[r.text for r in results])
        self.assertEqual(len({r.json()['receipt']['receipt_id'] for r in results}),1)
        self.assertEqual(sum(r.json()['created'] for r in results),1)

    async def test_no_class_retains_receipt_and_restore_invalidates_old_challenges(self):
        opened=await self.open();self.actor=1;accepted=await self.scan(opened['token']);self.actor=2
        state=await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/state',json={'state':'no_class','expected_version':0,'reason':'Synthetic holiday correction'})
        self.assertEqual(state.status_code,200,state.text)
        self.assertEqual((await self.client.get(f'/api/v1/attendance/sessions/{self.session_id}')).json()['students'][0]['status'],'no_class')
        restore=await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/state',json={'state':'scheduled','expected_version':1,'reason':'Synthetic restore correction'})
        self.assertEqual(restore.status_code,200,restore.text)
        self.actor=1
        self.assertEqual((await self.client.get('/api/v1/attendance/receipts/'+accepted.json()['receipt']['receipt_id'])).status_code,200)
        async with self.sessions() as db:
            session=await db.get(AttendanceSession,self.session_id)
            self.assertEqual(len(await s.scans_for(db,session.id)),1)
            self.assertEqual(session.version,2)
        # A different still-active member's first scan cannot reuse pre-toggle QR.
        async with self.sessions.begin() as db:
            entry=(await db.exec(select(AcademicRosterEntry).where(AcademicRosterEntry.class_id==20).order_by(AcademicRosterEntry.id))).all()[1]
            from src.db.academic_classes import SchoolStudent
            p=await db.get(SchoolStudent,entry.student_id);p.user_id=3;db.add(p)
        self.actor=3
        self.assertEqual((await self.scan(opened['token'])).status_code,410)

    async def test_expired_token_creates_no_evidence(self):
        opened=await self.open()
        async with self.sessions.begin() as db:
            await roster.serialize(db)
            with self.assertRaises(HTTPException) as error:
                await s.accept_scan(db,opened['token'],await db.get(User,1),1,self.now+timedelta(minutes=3))
            self.assertEqual(error.exception.status_code,410)
        async with self.sessions() as db:self.assertEqual(len((await db.exec(select(AttendanceScan))).all()),0)

    async def test_withdrawn_or_wrong_class_student_denied(self):
        opened=await self.open();self.actor=3
        self.assertEqual((await self.scan(opened['token'])).status_code,403)
        self.actor=1
        async with self.sessions.begin() as db:
            entry=(await db.exec(select(AcademicRosterEntry).join(SchoolStudent).where(SchoolStudent.user_id==1))).one()
            entry.status='withdrawn';db.add(entry)
        self.assertEqual((await self.scan(opened['token'])).status_code,403)

    async def test_revoked_teacher_cannot_open_or_change_state(self):
        async with self.sessions.begin() as db:
            assignment=(await db.exec(select(TeachingAssignment).where(TeachingAssignment.user_id==2))).one();assignment.active=False;db.add(assignment)
        for path,body in ((f'/sessions/{self.session_id}/open',{'kind':'entry'}),(f'/sessions/{self.session_id}/state',{'state':'no_class','expected_version':0,'reason':'Synthetic cancellation'})):
            response=await self.client.post('/api/v1/attendance'+path,json=body);self.assertEqual(response.status_code,403,response.text)

    async def test_other_actor_cannot_read_receipt(self):
        opened=await self.open();self.actor=1;accepted=await self.scan(opened['token']);self.actor=3
        response=await self.client.get('/api/v1/attendance/receipts/'+accepted.json()['receipt']['receipt_id'])
        self.assertEqual(response.status_code,404)

    async def test_foreign_origin_and_malformed_token_denied(self):
        response=await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/open',json={'kind':'entry'},headers={'Origin':'https://evil.example'})
        self.assertEqual(response.status_code,403,response.text)
        self.assertEqual((await self.scan('invalid')).status_code,422)

    async def test_timezone_and_policy_validation(self):
        base={'title':'Synthetic','starts_at':self.now.isoformat(),'ends_at':(self.now+timedelta(hours=1)).isoformat()}
        for changes in ({'starts_at':'2026-10-14T09:00:00'},{'timezone':'Not/AZone'},{'late_threshold_minutes':3},{'grace_minutes':True},{'ends_at':base['starts_at']}):
            response=await self.client.post('/api/v1/attendance/classes/20/sessions',json={**base,**changes})
            self.assertEqual(response.status_code,422,response.text)

    async def test_stale_state_fails_and_no_class_cannot_open(self):
        response=await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/state',json={'state':'no_class','expected_version':1,'reason':'Synthetic holiday'})
        self.assertEqual(response.status_code,409)
        response=await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/state',json={'state':'no_class','expected_version':0,'reason':'Synthetic holiday'})
        self.assertEqual(response.status_code,200)
        response=await self.client.post(f'/api/v1/attendance/sessions/{self.session_id}/open',json={'kind':'entry'})
        self.assertEqual(response.status_code,409)

    async def test_evidence_cannot_be_changed_deleted_or_truncated(self):
        opened=await self.open();self.actor=1;await self.scan(opened['token'])
        statements=["UPDATE attendancescan SET computed_status='late'",'DELETE FROM attendancescan','TRUNCATE attendancescan',"UPDATE attendancechallenge SET token_hash='changed'",'DELETE FROM attendancechallenge',"UPDATE attendancesession SET class_id=999",'DELETE FROM attendancesession',"UPDATE attendanceevent SET kind='changed'",'DELETE FROM attendanceevent']
        for statement in statements:
            with self.subTest(statement=statement), self.assertRaises(Exception):
                async with self.sessions.begin() as db:await db.execute(text(statement))

    async def test_anonymous_actor_headers_cannot_authorize_attendance(self):
        from src.routers.school_identity import context as native_context
        with patch.object(api, 'context', native_context):
            response=await self.client.post('/api/v1/attendance/check-in',json={'token':'a'*43},headers={'X-User-Id':'1'})
            self.assertEqual(response.status_code,401,response.text)
            response=await self.client.get('/api/v1/attendance/classes/20/sessions')
            self.assertEqual(response.status_code,401,response.text)

    async def test_frozen_deployment_sql_matches_models_and_guards(self):
        from pathlib import Path
        import sqlalchemy as sa
        async with self.engine.begin() as conn:
            for table in reversed(ATTENDANCE_TABLES):await conn.run_sync(table.drop)
        async with self.engine.connect() as conn:
            raw=await conn.get_raw_connection()
            await raw.driver_connection.execute(Path('/deployment/attendance-schema.sql').read_text())
        async with self.engine.begin() as conn:
            def check(sync):
                for table in ATTENDANCE_TABLES:self.assertEqual({c['name'] for c in sa.inspect(sync).get_columns(table.name)},set(table.columns.keys()))
            await conn.run_sync(check)
            triggers=(await conn.execute(text("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal AND tgrelid IN ('attendancesession'::regclass,'attendancechallenge'::regclass,'attendancescan'::regclass,'attendanceevent'::regclass)"))).scalar_one()
            self.assertEqual(triggers,9)

    async def test_migration_models_match_and_downgrade_refuses(self):
        import importlib.util
        import sqlalchemy as sa
        from pathlib import Path
        from alembic.operations import Operations
        from alembic.migration import MigrationContext
        spec=importlib.util.spec_from_file_location('attendance_migration',Path('migrations/versions/f36da41e9f33_class_attendance.py'))
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        def check(conn):
            for table in reversed(ATTENDANCE_TABLES):table.drop(conn)
            with Operations.context(MigrationContext.configure(conn)):migration.upgrade()
            for table in ATTENDANCE_TABLES:self.assertEqual({c['name'] for c in sa.inspect(conn).get_columns(table.name)},set(table.columns.keys()))
            with Operations.context(MigrationContext.configure(conn)):
                with self.assertRaises(RuntimeError):migration.downgrade()
        async with self.engine.begin() as conn:await conn.run_sync(check)
