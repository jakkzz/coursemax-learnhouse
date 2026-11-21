"""Real disposable PostgreSQL races; synthetic fetches, never the registrar."""
import asyncio
from datetime import timedelta
import time
import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlmodel import select

from src.route66_ext.tests.services.test_academic_rosters import AcademicRosterTests
from src.route66_ext.db.academic_classes import AcademicClass, AcademicClassEvent, AcademicRosterEntry, TeachingAssignment
from src.route66_ext.db.roster_refresh import AcademicRosterRefresh
from src.route66_ext.services import academic_rosters as roster, roster_refresh as service, roster_refresh_worker as worker


class RefreshTests(AcademicRosterTests):
    async def prepare(self, count=2):
        await self.snapshot(*(str(6900000000 + i) for i in range(1, count + 1)))
        await self.due()

    async def due(self):
        async with self.sessions.begin() as db:
            await roster.serialize(db)
            cls = await db.get(AcademicClass, 20)
            cls.last_synced_at = service.utcnow() - timedelta(hours=7)
            db.add(cls)
            state = await service.state_for(db, cls)
            state.next_check_at = service.utcnow() - timedelta(seconds=1)
            db.add(state)

    async def entries(self):
        async with self.sessions() as db:
            return [(e.id, e.status, e.missing_count, e.source) for e in
                    (await db.exec(select(AcademicRosterEntry).order_by(AcademicRosterEntry.id))).all()]

    async def test_identical_separate_observations_and_lost_ack(self):
        await self.prepare()
        first = await service.claim_one(self.sessions, 1)
        rows = self.rows('6900000001')
        result = await service.complete(self.sessions, 1, first, rows, 'b'*64)
        self.assertEqual(result['counts']['withdrawn'], 0)
        self.assertEqual((await service.complete(self.sessions, 1, first, rows, 'b'*64))['outcome'], 'superseded')
        self.assertEqual((await self.entries())[1][2], 1)
        await self.due()
        second = await service.claim_one(self.sessions, 1)
        result = await service.complete(self.sessions, 1, second, rows, 'b'*64)
        self.assertEqual(result['counts']['withdrawn'], 1)
        async with self.sessions() as db:
            events = (await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.actor_user_id.is_(None)))).all()
            self.assertTrue(events)
            self.assertTrue(all(e.details['origin'] == 'scheduled' and len(e.details['refresh_run_id']) == 32 for e in events))
            self.assertEqual((await db.get(AcademicRosterRefresh, 20)).lease_id, None)

    async def test_duplicate_claims_and_expired_worker_are_fenced(self):
        await self.prepare()
        claims = await asyncio.gather(service.claim_one(self.sessions, 1), service.claim_one(self.sessions, 1))
        claimed = [c for c in claims if c]
        self.assertEqual(len(claimed), 1)
        future = service.utcnow() + timedelta(seconds=121)
        replacement = await service.claim_one(self.sessions, 1, now=future)
        self.assertIsNotNone(replacement)
        self.assertNotEqual(replacement.token, claimed[0].token)
        before = await self.entries()
        self.assertEqual((await service.complete(self.sessions, 1, claimed[0], self.rows('6900000001'), 'b'*64, now=future))['outcome'], 'superseded')
        self.assertEqual(await self.entries(), before)
        self.assertEqual((await service.complete(self.sessions, 1, replacement, self.rows('6900000001'), 'b'*64, now=future))['outcome'], 'applied')

    async def test_large_drop_one_confirmation_then_consumed(self):
        await self.prepare(12)
        rows = self.rows('6900000001')
        claim = await service.claim_one(self.sessions, 1)
        before = await self.entries()
        self.assertEqual((await service.complete(self.sessions, 1, claim, rows, 'b'*64))['outcome'], 'needs_review')
        self.assertEqual(await self.entries(), before)
        async with self.sessions.begin() as db:
            await roster.serialize(db)
            result = await service.accept(db, await db.get(AcademicClass, 20), rows, 'b'*64, 2, confirm_large_drop=True)
            self.assertEqual(result['outcome'], 'applied')
        await self.due()
        claim = await service.claim_one(self.sessions, 1)
        result = await service.complete(self.sessions, 1, claim, rows, 'b'*64)
        self.assertEqual(result['counts']['withdrawn'], 11)
        async with self.sessions() as db:
            self.assertIsNone((await db.get(AcademicRosterRefresh, 20)).approved_drop)

    async def test_large_drop_approval_does_not_survive_membership_edit(self):
        await self.prepare(12)
        async with self.sessions.begin() as db:
            await roster.serialize(db)
            cls = await db.get(AcademicClass, 20)
            await service.accept(db, cls, self.rows('6900000001'), 'b'*64, 2, confirm_large_drop=True)
            cls.version += 1
            db.add(cls)
        await self.due()
        claim = await service.claim_one(self.sessions, 1)
        self.assertEqual((await service.complete(self.sessions, 1, claim, self.rows('6900000001'), 'b'*64))['outcome'], 'needs_review')
        self.assertTrue(all(e[1] == 'active' for e in await self.entries()))

    async def test_semantically_identical_recent_html_cannot_count_twice(self):
        await self.prepare()
        rows = self.rows('6900000001')
        first = await service.claim_one(self.sessions, 1)
        await service.complete(self.sessions, 1, first, rows, 'b'*64)
        async with self.sessions.begin() as db:
            state = await db.get(AcademicRosterRefresh, 20)
            state.next_check_at = service.utcnow()
            db.add(state)
        second = await service.claim_one(self.sessions, 1)
        result = await service.complete(self.sessions, 1, second, rows, 'c'*64)
        self.assertEqual(result['outcome'], 'recently_applied')
        self.assertEqual((await self.entries())[1][2], 1)

    async def test_pause_resume_during_fetch_fences_old_token(self):
        await self.prepare()
        claimed = await service.claim_one(self.sessions, 1)
        async with self.sessions.begin() as db:
            await roster.serialize(db)
            state = await service.state_for(db, await db.get(AcademicClass, 20))
            state.control_version += 2
            state.lease_id = state.lease_until = None
            db.add(state)
        self.assertEqual((await service.complete(self.sessions, 1, claimed, self.rows('6900000001'), 'b'*64))['outcome'], 'superseded')
        self.assertTrue(all(e[2] == 0 for e in await self.entries()))

    async def test_manual_apply_wins_fetch_race(self):
        await self.prepare()
        claimed = await service.claim_one(self.sessions, 1)
        async with self.sessions.begin() as db:
            await roster.serialize(db)
            await service.accept(db, await db.get(AcademicClass, 20), self.rows('6900000001', '6900000002'), 'c'*64, 2)
        self.assertEqual((await service.complete(self.sessions, 1, claimed, self.rows('6900000001'), 'b'*64))['outcome'], 'superseded')
        self.assertTrue(all(e[2] == 0 for e in await self.entries()))

    async def test_source_and_authority_changes_discard_fetch(self):
        await self.prepare()
        claimed = await service.claim_one(self.sessions, 1)
        async with self.sessions.begin() as db:
            cls = await db.get(AcademicClass, 20)
            cls.section = 'P2'
            db.add(cls)
        self.assertEqual((await service.complete(self.sessions, 1, claimed, self.rows('6900000001'), 'b'*64))['outcome'], 'stale')
        await self.due()
        claimed = await service.claim_one(self.sessions, 1)
        async with self.sessions.begin() as db:
            assignment = (await db.exec(select(TeachingAssignment))).one()
            assignment.active = False
            db.add(assignment)
        self.assertEqual((await service.complete(self.sessions, 1, claimed, self.rows('6900000001'), 'b'*64))['outcome'], 'authority_changed')
        self.assertTrue(all(e[2] == 0 for e in await self.entries()))

    async def test_invalid_source_never_advances_missing(self):
        await self.prepare()
        claimed = await service.claim_one(self.sessions, 1)
        result = await service.run_one(self.sessions, 1, claimed, fetch=AsyncMock(side_effect=ValueError('synthetic invalid')))
        self.assertEqual(result['outcome'], 'source_failed')
        self.assertTrue(all(e[2] == 0 for e in await self.entries()))

    async def test_writer_failure_rolls_back_partial_membership_and_records_failure(self):
        await self.prepare()
        before = await self.entries()
        claimed = await service.claim_one(self.sessions, 1)
        original = roster.apply_roster
        async def failing(*args, **kwargs):
            await original(*args, **kwargs)
            raise RuntimeError('synthetic crash before commit')
        with patch.object(roster, 'apply_roster', side_effect=failing):
            result = await service.run_one(self.sessions, 1, claimed, fetch=AsyncMock(return_value=(self.rows('6900000001'), 'b'*64)))
        self.assertEqual(result['outcome'], 'write_failed')
        self.assertEqual(await self.entries(), before)

    async def test_redis_loss_or_other_leader_never_claims(self):
        redis = AsyncMock()
        redis.eval.return_value = 0
        redis.set.return_value = False
        with patch.object(service, 'claim_one', new_callable=AsyncMock) as claim:
            self.assertFalse(await worker.tick(self.sessions, redis, 'fixture', 'token', 1))
            claim.assert_not_called()
        redis.eval.side_effect = RuntimeError('synthetic Redis outage')
        with patch.object(service, 'claim_one', new_callable=AsyncMock) as claim:
            with self.assertRaises(RuntimeError):
                await worker.tick(self.sessions, redis, 'fixture', 'token', 1)
            claim.assert_not_called()

    async def test_calendar_only_never_initialises_or_fetches(self):
        await service.initialise(self.sessions, 1)
        self.assertIsNone(await service.claim_one(self.sessions, 1))
        async with self.sessions() as db:
            self.assertIsNone(await db.get(AcademicRosterRefresh, 20))

    async def test_verified_unmatched_owner_and_retired_proof(self):
        from src.route66_ext.db.school_identity import SchoolGoogleEvidence, NrruTeacherIdentity
        from src.route66_ext.db.provider_identity import ProviderIdentity
        await self.claim(user=2, number='teacher.fixture')
        async with self.sessions.begin() as db:
            proof = (await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id == 2))).one()
            db.add(NrruTeacherIdentity(user_id=2, identity_id=proof.identity_id, officer_id='300', officer_code='fixture', name_th='ผู้สอนตัวอย่าง', name_en='Synthetic teacher'))
            cls = AcademicClass(id=21, org_id=1, course_id=None, teacher_user_id=2,
                academic_year=2568, semester=2, section='P2', registry_course_id='101', registry_class_id=None, registry_course_code='990002')
            db.add(cls); await db.flush(); await roster.serialize(db)
            await service.accept(db, cls, self.rows('6900000001'), 'a'*64, 2)
            cls.last_synced_at = service.utcnow() - timedelta(hours=7)
            state = await db.get(AcademicRosterRefresh, 21)
            state.next_check_at = service.utcnow()
            db.add(cls); db.add(state)
        claim = await service.claim_one(self.sessions, 1)
        self.assertEqual(claim.class_id, 21)
        self.assertEqual((await service.complete(self.sessions, 1, claim, self.rows('6900000001'), 'b'*64))['outcome'], 'applied')
        async with self.sessions.begin() as db:
            proof = (await db.exec(select(ProviderIdentity).where(ProviderIdentity.user_id == 2))).one()
            proof.retired_at = service.utcnow(); proof.retirement_reason = 'Synthetic proof retirement'; db.add(proof)
            state = await db.get(AcademicRosterRefresh, 21)
            state.next_check_at = service.utcnow(); db.add(state)
        self.assertIsNone(await service.claim_one(self.sessions, 1))
        async with self.sessions() as db:
            self.assertEqual((await db.get(AcademicRosterRefresh, 21)).status, 'authority_changed')

    async def test_null_class_id_is_valid_scheduled_source(self):
        await self.prepare()
        async with self.sessions.begin() as db:
            cls = await db.get(AcademicClass, 20)
            cls.registry_class_id = None
            db.add(cls)
        claim = await service.claim_one(self.sessions, 1)
        self.assertIsNone(claim.source['registry_class_id'])
        result = await service.complete(self.sessions, 1, claim, self.rows('6900000001'), 'b'*64)
        self.assertEqual(result['source_kind'], 'course_rtf')

    async def test_try_lock_defers_without_waiting(self):
        await self.prepare()
        claim = await service.claim_one(self.sessions, 1)
        async with self.sessions.begin() as interactive:
            await roster.serialize(interactive)
            result = await asyncio.wait_for(service.complete(self.sessions, 1, claim, self.rows('6900000001'), 'b'*64), 3)
        self.assertEqual(result['outcome'], 'retrying')
        self.assertTrue(all(e[2] == 0 for e in await self.entries()))

    async def test_sql_actor_constraint_and_append_only_history(self):
        for details in ({}, {'origin': 'scheduled'}, {'origin': 'scheduled', 'refresh_run_id': 'bad'}):
            with self.assertRaises(IntegrityError):
                async with self.sessions.begin() as db:
                    db.add(AcademicClassEvent(kind='roster_refresh_finished', details=details))
                    await db.flush()
        async with self.sessions.begin() as db:
            event = roster.event(db, roster.ScheduledActor('a'*32), 'roster_refresh_finished', {}, await db.get(AcademicClass, 20))
            await db.flush()
            ident = event.id
        with self.assertRaises(DBAPIError):
            async with self.sessions.begin() as db:
                await db.execute(text('DELETE FROM academicclassevent WHERE id=:id'), {'id': ident})

    async def test_one_connection_is_released_while_fetching(self):
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlmodel.ext.asyncio.session import AsyncSession
        await self.prepare()
        engine = create_async_engine(self.engine.url, connect_args={'host': '/scratch',
            'server_settings': {'search_path': self.schema}}, pool_size=1, max_overflow=0, pool_timeout=.5)
        sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async def fetch(cls):
            async with sessions() as db:
                self.assertEqual((await db.execute(text('SELECT 1'))).scalar(), 1)
            return self.rows('6900000001'), 'b'*64
        try:
            claim = await service.claim_one(sessions, 1)
            self.assertEqual((await service.run_one(sessions, 1, claim, fetch=fetch))['outcome'], 'applied')
        finally:
            await engine.dispose()

    async def test_connection_loss_rolls_back_before_failure_receipt(self):
        await self.prepare()
        before = await self.entries()
        claim = await service.claim_one(self.sessions, 1)
        original = roster.apply_roster
        async def disconnect(db, *args, **kwargs):
            result = await original(db, *args, **kwargs)
            pid = (await db.execute(text('SELECT pg_backend_pid()'))).scalar()
            async with self.admin.begin() as admin:
                await admin.execute(text('SELECT pg_terminate_backend(:pid)'), {'pid': pid})
            await db.execute(text('SELECT 1'))
            return result
        with patch.object(roster, 'apply_roster', side_effect=disconnect):
            result = await service.run_one(self.sessions, 1, claim, fetch=AsyncMock(return_value=(self.rows('6900000001'), 'b'*64)))
        self.assertEqual(result['outcome'], 'write_failed')
        self.assertEqual(await self.entries(), before)

    async def test_lease_expiring_during_write_rolls_back(self):
        await self.prepare()
        claim = await service.claim_one(self.sessions, 1)
        before = await self.entries()
        original = roster.apply_roster
        now = service.utcnow()
        with patch.object(service, 'utcnow', return_value=now) as clock:
            async def slow(*args, **kwargs):
                result = await original(*args, **kwargs)
                clock.return_value = now + timedelta(seconds=121)
                return result
            with patch.object(roster, 'apply_roster', side_effect=slow):
                with self.assertRaises(service.LeaseExpired):
                    await service.complete(self.sessions, 1, claim, self.rows('6900000001'), 'b'*64)
        self.assertEqual(await self.entries(), before)

    async def test_migration_preserves_humans_and_refuses_history_downgrade(self):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from src.route66_ext.migrations.versions import e6bc47a4da35_roster_refresh as migration
        await self.snapshot('6900000001')
        async with self.sessions() as db:
            before = [e.model_dump() for e in (await db.exec(select(AcademicClassEvent).order_by(AcademicClassEvent.id))).all()]
        def migrate(connection, direction='upgrade'):
            with Operations.context(MigrationContext.configure(connection)):
                getattr(migration, direction)()
        async with self.engine.begin() as connection:
            await connection.execute(text('DROP TABLE academicrosterrefresh'))
            await connection.execute(text('ALTER TABLE academicclassevent DROP CONSTRAINT ck_academic_event_actor'))
            await connection.execute(text('ALTER TABLE academicclassevent ALTER COLUMN actor_user_id SET NOT NULL'))
            await connection.execute(text('DROP INDEX ix_academic_roster_refresh_history'))
            await connection.run_sync(migrate)
            await connection.run_sync(migrate)
        async with self.sessions.begin() as db:
            self.assertEqual([e.model_dump() for e in (await db.exec(select(AcademicClassEvent).order_by(AcademicClassEvent.id))).all()], before)
            roster.event(db, roster.ScheduledActor('f'*32), 'roster_refresh_finished', {}, await db.get(AcademicClass, 20))
        async with self.engine.begin() as connection:
            with self.assertRaisesRegex(RuntimeError, 'Keep scheduled'):
                await connection.run_sync(lambda c: migrate(c, 'downgrade'))
        # Current untyped history DTO also used by the retained parent reader.
        from src.route66_ext.routers import academic_classes as api
        from contextlib import ExitStack
        from fastapi import Response
        async with self.sessions() as db:
            with ExitStack() as stack:
                for p in await self.endpoint_context(db): stack.enter_context(p)
                result = await api.roster(20, None, Response(), db)
                self.assertEqual(result['events'][0]['details']['origin'], 'scheduled')

    async def test_named_migration_and_retained_parent_reader(self):
        import importlib.util, os, subprocess
        from pathlib import Path
        private = os.getenv('LEARNHOUSE_TEST_PRIVATE_SOURCE')
        if not private or not (Path(private)/'parent/apps/api').is_dir():
            self.skipTest('Provide the exact retained-parent source for the rollback reader proof')
        await self.snapshot('6900000001')
        async with self.engine.begin() as connection:
            await connection.execute(text('DROP TABLE academicrosterrefresh'))
            await connection.execute(text('ALTER TABLE academicclassevent DROP CONSTRAINT ck_academic_event_actor'))
            await connection.execute(text('ALTER TABLE academicclassevent ALTER COLUMN actor_user_id SET NOT NULL'))
            await connection.execute(text('DROP INDEX ix_academic_roster_refresh_history'))
        spec = importlib.util.spec_from_file_location('named_refresh_migration', '/deployment/apply_roster_refresh_migration.py')
        named = importlib.util.module_from_spec(spec); spec.loader.exec_module(named)
        with patch.dict(os.environ, {'LEARNHOUSE_SQL_CONNECTION_STRING': 'postgresql://fixture@/fixture?host=/scratch&options=-csearch_path%3D'+self.schema}):
            await asyncio.to_thread(named.main)
        await self.due()
        claim = await service.claim_one(self.sessions, 1)
        await service.complete(self.sessions, 1, claim, self.rows('6900000001'), 'b'*64)
        env = {**os.environ, 'PYTHONPATH': str(Path(private)/'parent/apps/api')}
        result = await asyncio.to_thread(subprocess.run,
            ['/app/api/.venv/bin/python', '-B', str(Path(__file__).with_name('roster_refresh_parent_reader.py')), self.schema],
            cwd=str(Path(private)/'parent/apps/api'), env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        print(result.stdout.strip())

    async def test_http_manager_controls_coalesce_and_deny_students(self):
        import httpx
        from contextlib import asynccontextmanager
        from types import SimpleNamespace
        from fastapi import FastAPI
        from src.route66_ext.routers import roster_refresh as api
        from src.route66_ext.adapters.db_users import User
        await self.prepare()
        app = FastAPI(); app.include_router(api.router)
        async def database():
            async with self.sessions() as db: yield db
        async def context(request, db):
            return await db.get(User, int(request.headers.get('x-fixture-user', '2'))), SimpleNamespace(org_id=1), None
        @asynccontextmanager
        async def resources(config): yield AsyncMock(), None
        app.dependency_overrides[api.get_db_session] = database
        with patch.object(api, 'context', context), patch.object(api, 'boundary', lambda *args: None), patch.object(api, 'resources', resources), patch.object(api, 'throttle', AsyncMock()):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='https://fixture.invalid') as client:
                for method, path, body in [('GET', '', None), ('POST', '/check', {}), ('POST', '/settings', {'paused': True, 'expected_version': 0})]:
                    response = await client.request(method, '/20/roster/refresh'+path, json=body, headers={'x-fixture-user': '3'})
                    self.assertEqual(response.status_code, 403)
                for _ in range(2):
                    self.assertEqual((await client.post('/20/roster/refresh/check')).status_code, 202)
                self.assertEqual((await client.post('/20/roster/refresh/settings', json={'paused': True, 'expected_version': 0})).status_code, 200)
                self.assertEqual((await client.post('/20/roster/refresh/check')).status_code, 409)
                self.assertEqual((await client.post('/20/roster/refresh/settings', json={'paused': False, 'expected_version': 0})).status_code, 409)
                status = await client.get('/20/roster/refresh')
                self.assertTrue(status.json()['paused'])
                self.assertIn('no-store', status.headers['cache-control'])
        async with self.sessions() as db:
            self.assertEqual(len((await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind=='roster_refresh_requested'))).all()), 1)

    async def test_router_lifecycle_composes_and_cancels_before_native_shutdown(self):
        from contextlib import asynccontextmanager
        from fastapi import FastAPI, APIRouter
        from src.route66_ext.adapters import core_events_database
        events = []
        @asynccontextmanager
        async def native(app):
            events.append('native_start')
            yield {'native_state': 42}
            events.append('native_stop')
        async def run(sessions):
            events.append('worker_start')
            try: await asyncio.Future()
            finally: events.append('worker_stop')
        app = FastAPI(lifespan=native)
        app.include_router(APIRouter(lifespan=worker.lifespan))
        with patch.object(worker, 'run', run), patch.object(core_events_database, 'engine', self.engine):
            async with app.router.lifespan_context(app) as state:
                await asyncio.sleep(0)
                self.assertEqual(state['native_state'], 42)
        self.assertEqual(events, ['native_start', 'worker_start', 'worker_stop', 'native_stop'])

    async def test_thousand_rows_preserve_per_member_evidence(self):
        start = time.monotonic()
        await self.prepare(1000)
        claim = await service.claim_one(self.sessions, 1)
        rows = self.rows(*(str(6900000000 + i) for i in range(1, 1001)))
        result = await service.complete(self.sessions, 1, claim, rows, 'b'*64)
        self.assertEqual(result['outcome'], 'applied')
        async with self.sessions() as db:
            count = (await db.execute(text("SELECT count(*) FROM academicclassevent WHERE details->>'refresh_run_id'=:run"), {'run': claim.token})).scalar()
            self.assertGreaterEqual(count, 1002)
            size = (await db.execute(text('SELECT pg_total_relation_size(\'academicclassevent\')'))).scalar()
        print({'fixture_students': 1000, 'scheduled_events': count, 'history_bytes': size, 'seconds': round(time.monotonic()-start, 2)})


from src.route66_ext.tests.services.test_learning_access import LearningAccessTests


class ScheduledAccessTests(LearningAccessTests, RefreshTests):
    async def test_system_attributed_access_failure_keeps_roster_and_manual_grants(self):
        from src.route66_ext.adapters.native_learning_access_test_support import UserGroupUser
        from fastapi import HTTPException
        await self.active(); await self.configure()
        async with self.sessions.begin() as db:
            db.add(UserGroupUser(usergroup_id=30, org_id=1, user_id=2, creation_date='manual', update_date='manual'))
        await self.due()
        claim = await service.claim_one(self.sessions, 1)
        with patch('src.route66_ext.adapters.native_learning_access.check_org_plan', new=AsyncMock(side_effect=HTTPException(403, 'Synthetic plan loss'))):
            result = await service.complete(self.sessions, 1, claim, self.rows('6900000001'), 'b'*64)
        self.assertEqual(result['outcome'], 'applied')
        self.assertEqual([m.user_id for m in await self.members()], [2])
        async with self.sessions() as db:
            pending = (await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind == 'learning_access_pending'))).one()
            self.assertIsNone(pending.actor_user_id)
            self.assertEqual(pending.details['refresh_run_id'], claim.token)
        await self.due()
        second = await service.claim_one(self.sessions, 1)
        self.assertEqual((await service.complete(self.sessions, 1, second, self.rows('6900000001'), 'b'*64))['outcome'], 'applied')
        self.assertTrue(await self.decision(1))


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(case(name) for case in (RefreshTests, ScheduledAccessTests)
                              for name in case.__dict__ if name.startswith('test_'))
