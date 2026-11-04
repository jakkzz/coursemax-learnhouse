"""Synthetic persisted review workflows; no native-account/evidence reassignment."""
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, HTTPException, Response
import httpx
from sqlmodel import select

from src.route66_ext.tests.services.test_academic_rosters import AcademicRosterTests
from src.route66_ext.db.academic_classes import AcademicClass, AcademicClassEvent, AcademicRosterEntry, SchoolStudent
from src.route66_ext.db.school_identity import SchoolGoogleEvidence
from src.route66_ext.adapters.db_users import User
from src.route66_ext.services import academic_rosters as roster, identity_reviews as reviews
from src.route66_ext.routers import academic_classes as classes, identity_reviews as api


class IdentityReviewTests(AcademicRosterTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.sessions.begin() as db:
            admin = await db.get(User, 3); admin.is_superadmin = True; db.add(admin)

    async def make_case(self, *, own=False):
        async with self.sessions.begin() as db:
            await roster.serialize(db)
            profile = (await db.exec(select(SchoolStudent).where(SchoolStudent.student_number == '6900000001'))).one()
            cls = None if own else await db.get(AcademicClass, 20)
            case = await reviews.request_review(db, 1 if own else 2, 1, profile, 'Synthetic identity discrepancy', cls)
            return case.id

    async def digest(self, db):
        return ([p.model_dump() for p in (await db.exec(select(SchoolStudent).order_by(SchoolStudent.id))).all()],
                [e.model_dump() for e in (await db.exec(select(AcademicRosterEntry).order_by(AcademicRosterEntry.id))).all()])

    async def test_teacher_flag_reuses_open_request_and_preserves_membership(self):
        await self.snapshot('6900000001')
        async with self.sessions() as db:
            before = await self.digest(db)
            entry = (await db.exec(select(AcademicRosterEntry))).one()
            with ExitStack() as stack:
                for p in await self.endpoint_context(db): stack.enter_context(p)
                first = await classes.flag(20, entry.id, classes.Flag(reason='Synthetic discrepancy'), None, Response(), db)
                second = await classes.flag(20, entry.id, classes.Flag(reason='Synthetic discrepancy'), None, Response(), db)
                with self.assertRaises(HTTPException) as error:
                    await classes.flag(20, entry.id, classes.Flag(reason='A different report must not disappear'), None, Response(), db)
                self.assertEqual(error.exception.status_code, 409)
            self.assertEqual(first['case_id'], second['case_id'])
            self.assertEqual(before, await self.digest(db))
            self.assertEqual(len((await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind == reviews.REQUEST))).all()), 1)

    async def test_admin_rechecks_exact_match_and_persists_decision(self):
        await self.claim(); await self.snapshot('6900000001')
        case_id = await self.make_case()
        async with self.sessions.begin() as db:
            before = await self.digest(db); case = await reviews.get_case(db, case_id, 1)
            old = await reviews.view(db, case, 1, reviewer=True)
            self.assertTrue(old['can_match'])
            result = await reviews.decide(db, 3, 1, case, 'recheck', 'Verified existing account', old['expected_token'])
            self.assertEqual((result['status'], result['outcome']), ('closed', 'matched'))
            self.assertEqual(before, await self.digest(db))
        async with self.sessions() as db:
            case = await reviews.get_case(db, case_id, 1)
            decision = await reviews.decision(db, case)
            self.assertEqual(decision.actor_user_id, 3)
            self.assertEqual(decision.details['reason'], 'Verified existing account')
            self.assertEqual((await reviews.view(db, case, 1))['status'], 'closed')
            self.assertFalse((await db.get(User, 1)).is_superadmin)

    async def test_deferred_exact_match_uses_existing_writer(self):
        await self.snapshot('6900000001')
        with patch.object(roster, 'reconcile_login', AsyncMock()):
            await self.claim()
        case_id = await self.make_case()
        async with self.sessions.begin() as db:
            case = await reviews.get_case(db, case_id, 1); view = await reviews.view(db, case, 1, reviewer=True)
            self.assertEqual(view['match_state'], 'ready_to_match')
            before = [(e.id, e.student_id, e.status) for e in (await db.exec(select(AcademicRosterEntry))).all()]
            await reviews.decide(db, 3, 1, case, 'recheck', 'Recheck after temporary outage', view['expected_token'])
            self.assertEqual((await db.get(SchoolStudent, case.student_id)).user_id, 1)
            self.assertEqual(before, [(e.id, e.student_id, e.status) for e in (await db.exec(select(AcademicRosterEntry))).all()])
            event = (await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind == 'student_identity_matched'))).one()
            self.assertEqual(event.actor_user_id, 3)

    async def test_multiple_claims_block_confirmation_but_allow_honest_unchanged_closure(self):
        await self.claim(); await self.snapshot('6900000001'); await self.claim(2)
        case_id = await self.make_case(own=True)
        async with self.sessions.begin() as db:
            case = await reviews.get_case(db, case_id, 1); view = await reviews.view(db, case, 1, reviewer=True)
            before = await self.digest(db)
            self.assertEqual(view['match_state'], 'multiple_claims'); self.assertFalse(view['can_match'])
            with self.assertRaises(HTTPException) as error:
                await reviews.decide(db, 3, 1, case, 'recheck', 'Cannot choose the owner', view['expected_token'])
            self.assertEqual(error.exception.status_code, 409)
            result = await reviews.decide(db, 3, 1, case, 'close', 'Keep existing ownership separate', view['expected_token'])
            self.assertEqual(result['outcome'], 'unchanged'); self.assertEqual(before, await self.digest(db))

    async def test_manual_and_registry_collision_cannot_merge_records(self):
        async with self.sessions.begin() as db:
            p = SchoolStudent(user_id=1, full_name_th='Manual fixture', faculty='', program='')
            db.add(p); await db.flush(); db.add(AcademicRosterEntry(class_id=20, student_id=p.id, source='manual', display_position=10))
        await self.snapshot('6900000001'); await self.claim(); case_id = await self.make_case()
        async with self.sessions.begin() as db:
            case = await reviews.get_case(db, case_id, 1); view = await reviews.view(db, case, 1, reviewer=True)
            before = await self.digest(db)
            self.assertEqual(view['match_state'], 'ownership_conflict')
            with self.assertRaises(HTTPException):
                await reviews.decide(db, 3, 1, case, 'recheck', 'Must preserve both records', view['expected_token'])
            self.assertEqual(before, await self.digest(db))

    async def test_changed_proof_rejects_stale_decision(self):
        await self.claim(); await self.snapshot('6900000001'); case_id = await self.make_case()
        async with self.sessions() as db:
            token = (await reviews.view(db, await reviews.get_case(db, case_id, 1), 1, reviewer=True))['expected_token']
        await self.claim(2)
        async with self.sessions.begin() as db:
            case = await reviews.get_case(db, case_id, 1)
            with self.assertRaises(HTTPException) as error:
                await reviews.decide(db, 3, 1, case, 'close', 'A stale review cannot close this', token)
            self.assertEqual(error.exception.status_code, 409); self.assertIsNone(await reviews.decision(db, case))

    async def test_second_decision_cannot_overwrite_first(self):
        await self.snapshot('6900000001'); case_id = await self.make_case()
        async with self.sessions.begin() as db:
            case = await reviews.get_case(db, case_id, 1); token = (await reviews.view(db, case, 1, reviewer=True))['expected_token']
            await reviews.decide(db, 3, 1, case, 'close', 'Keep identity unchanged', token)
            with self.assertRaises(HTTPException):
                await reviews.decide(db, 3, 1, case, 'close', 'Another administrator decision', token)
            self.assertEqual(len((await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind == reviews.DECISION))).all()), 1)

    async def test_concurrent_administrators_append_only_one_decision(self):
        import asyncio
        await self.snapshot('6900000001'); case_id = await self.make_case()
        async with self.sessions() as db:
            token = (await reviews.view(db, await reviews.get_case(db, case_id, 1), 1, reviewer=True))['expected_token']
        async def decide():
            try:
                async with self.sessions.begin() as db:
                    await roster.serialize(db)
                    await reviews.decide(db, 3, 1, await reviews.get_case(db, case_id, 1), 'close', 'Concurrent unchanged decision', token)
                return 200
            except HTTPException as error:
                return error.status_code
        self.assertEqual(sorted(await asyncio.gather(decide(), decide())), [200, 409])
        async with self.sessions() as db:
            self.assertEqual(len((await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind == reviews.DECISION))).all()), 1)

    async def test_own_case_cannot_be_reported_matched_to_another_account(self):
        await self.claim(); await self.snapshot('6900000001')
        async with self.sessions.begin() as db:
            profile = (await db.exec(select(SchoolStudent))).one()
            case = await reviews.request_review(db, 2, 1, profile, 'Previously claimed account needs review')
            view = await reviews.view(db, case, 1, reviewer=True)
            self.assertEqual(view['match_state'], 'original_account_needed')
            with self.assertRaises(HTTPException):
                await reviews.decide(db, 3, 1, case, 'recheck', 'Cannot confirm somebody else', view['expected_token'])
            self.assertEqual(profile.user_id, 1)

    async def test_own_review_is_private_and_organization_scoped(self):
        await self.claim(); await self.snapshot('6900000001'); case_id = await self.make_case(own=True)
        async with self.sessions() as db:
            evidence = (await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id == 1))).one()
            self.assertIsNotNone(await reviews.own_profile(db, 1, 1, evidence))
            self.assertIsNone(await reviews.own_profile(db, 1, 2, evidence))
            with self.assertRaises(HTTPException): await reviews.get_case(db, case_id, 2)
            own = await reviews.view(db, await reviews.get_case(db, case_id, 1), 1)
            for key in ('accounts', 'student_name', 'expected_token', 'decision_reason'):
                self.assertNotIn(key, own)
            self.assertNotIn('@nrru.ac.th', str(own))

    async def test_http_student_teacher_and_admin_workflow(self):
        await self.claim(); await self.snapshot('6900000001')
        app = FastAPI(); app.include_router(classes.router, prefix='/academic-classes')
        actor = [1]
        async def database():
            async with self.sessions() as db: yield db
        async def context(request, db):
            user = await db.get(User, actor[0])
            evidence = (await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id == user.id))).first()
            return user, SimpleNamespace(org_id=1), evidence
        app.dependency_overrides[api.get_db_session] = database
        with patch.object(api, 'context', context), patch.object(api, 'boundary', lambda *args: None), patch.object(classes, 'context', context):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='https://fixture.invalid') as client:
                self.assertEqual((await client.get('/academic-classes/identity-reviews')).status_code, 403)
                self.assertEqual((await client.post('/academic-classes/identity-reviews/own', json={'reason': '     '})).status_code, 422)
                first = await client.post('/academic-classes/identity-reviews/own', json={'reason': 'Please check my school record'})
                self.assertEqual(first.status_code, 200); case_id = first.json()['id']
                own = await client.get('/academic-classes/identity-reviews/own')
                self.assertIn('no-store', own.headers['cache-control']); self.assertEqual(own.json()['open_case_id'], case_id)
                self.assertEqual((await client.get(f'/academic-classes/identity-reviews/{case_id}')).status_code, 403)
                actor[0] = 2
                self.assertEqual((await client.get('/academic-classes/identity-reviews')).status_code, 403)
                self.assertEqual((await client.get('/academic-classes/identity-reviews/own')).json()['cases'], [])
                actor[0] = 3
                inbox = await client.get('/academic-classes/identity-reviews')
                self.assertEqual(inbox.status_code, 200); self.assertEqual(len(inbox.json()['cases']), 1)
                row = inbox.json()['cases'][0]
                result = await client.post(f'/academic-classes/identity-reviews/{case_id}/decision', json={
                    'action': 'recheck', 'reason': 'Verified exact current ownership', 'expected_token': row['expected_token']})
                self.assertEqual(result.status_code, 200); self.assertEqual(result.json()['outcome'], 'matched')
                self.assertEqual((await client.get('/academic-classes/identity-reviews')).json()['cases'], [])
                self.assertEqual(len((await client.get('/academic-classes/identity-reviews?status=closed')).json()['cases']), 1)
                actor[0] = 1
                self.assertEqual((await client.get('/academic-classes/identity-reviews/own')).json()['cases'][0]['status'], 'closed')


from src.route66_ext.tests.services.test_learning_access import LearningAccessTests


class IdentityReviewAccessTests(LearningAccessTests):
    async def pending(self):
        await self.snapshot('6900000001')
        with patch.object(roster, 'reconcile_login', AsyncMock()):
            await self.claim()
        await self.configure()
        async with self.sessions.begin() as db:
            profile = (await db.exec(select(SchoolStudent))).one()
            case = await reviews.request_review(db, 1, 1, profile, 'Please recheck deferred student match')
            return case.id

    async def test_school_classes_and_native_private_course_access_after_review(self):
        case_id = await self.pending()
        self.assertFalse(await self.decision(1))
        async with self.sessions.begin() as db:
            await roster.serialize(db)
            case = await reviews.get_case(db, case_id, 1); view = await reviews.view(db, case, 1, reviewer=True)
            await reviews.decide(db, 3, 1, case, 'recheck', 'Exact verified student match', view['expected_token'])
        self.assertTrue(await self.decision(1))
        from src.route66_ext.routers import school_identity
        from src.route66_ext.adapters.native_learning_access_test_support import PublicUser
        from starlette.requests import Request
        async with self.sessions() as db:
            user = PublicUser.model_validate(await db.get(User, 1))
            evidence = (await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id == 1))).one()
            async def context(*args): return user, SimpleNamespace(org_id=1), evidence
            with patch.object(school_identity, 'context', context), patch.object(classes, 'context', context):
                request = Request({'type': 'http', 'method': 'GET', 'path': '/', 'headers': []})
                school = await school_identity.own_identity(request, Response(), db)
                projection = await classes.classes(request, Response(), db)
            self.assertEqual(school['student_match_status'], 'matched')
            self.assertEqual(school['student_profile']['student_number'], '6900000001')
            self.assertEqual(len(projection['classes']), 1)
            self.assertTrue(projection['classes'][0]['course_available'])
            self.assertFalse(user.is_superadmin)

    async def test_optional_access_failure_keeps_match_and_manual_grant(self):
        case_id = await self.pending()
        from src.route66_ext.adapters.native_learning_access_test_support import UserGroupUser
        async with self.sessions.begin() as db:
            db.add(UserGroupUser(usergroup_id=30, org_id=1, user_id=2, creation_date='manual', update_date='manual'))
        with patch('src.route66_ext.adapters.native_learning_access.check_org_plan', AsyncMock(side_effect=HTTPException(503, 'Synthetic temporary access failure'))):
            async with self.sessions.begin() as db:
                case = await reviews.get_case(db, case_id, 1); view = await reviews.view(db, case, 1, reviewer=True)
                result = await reviews.decide(db, 3, 1, case, 'recheck', 'Identity is independently matched', view['expected_token'])
                self.assertEqual(result['outcome'], 'matched')
                self.assertEqual((await db.get(SchoolStudent, case.student_id)).user_id, 1)
        self.assertEqual([m.user_id for m in await self.members()], [2])
        async with self.sessions() as db:
            pending = (await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind == 'learning_access_pending'))).all()
            self.assertTrue(pending); self.assertEqual(pending[-1].actor_user_id, 3)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(cls(name) for cls in (IdentityReviewTests, IdentityReviewAccessTests)
                              for name in cls.__dict__ if name.startswith('test_'))
