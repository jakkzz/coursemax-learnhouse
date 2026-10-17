"""Real isolated PostgreSQL/native-RBAC integration, no live people or APIs."""
import copy
import os
import uuid
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlmodel import select
from starlette.requests import Request

from src.route66_ext.tests.services.test_academic_rosters import AcademicRosterTests
from src.route66_ext.services import learning_access as access, academic_rosters as roster
from src.route66_ext.db.academic_classes import AcademicClass, AcademicRosterEntry, AcademicClassEvent, SchoolStudent
from src.route66_ext.adapters.native_learning_access_test_support import (
    UserGroup, UserGroupResource, UserGroupUser, Course, Activity, ActivityTypeEnum,
    ActivitySubTypeEnum, ResourceAuthor, Trail, TrailRun, StatusEnum, TrailStep,
    User, PublicUser, AnonymousUser, OrganizationConfig, check_resource_access,
    AccessAction, get_db_session, native_courses_router, Chapter, CourseChapter,
)


class LearningAccessTests(AcademicRosterTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.engine.begin() as conn:
            from src.route66_ext.db.school_calendar import CALENDAR_TABLES
            for table in CALENDAR_TABLES:
                await conn.run_sync(table.create)
            for model in (UserGroup, UserGroupResource, UserGroupUser, ResourceAuthor, Trail, TrailRun, Activity, TrailStep):
                await conn.run_sync(model.__table__.create)
        async with self.sessions.begin() as db:
            from src.db.organization_config import OrganizationConfig
            db.add(OrganizationConfig(org_id=1, config={"config_version": "2.0", "plan": "standard"}))
            admin = await db.get(User, 3)
            admin.is_superadmin = True; admin.email_verified = True; db.add(admin)
            course = await db.get(Course, 10); course.published = True; db.add(course)
            db.add(UserGroup(id=30, org_id=1, name="Synthetic dedicated group", description="Fixture", usergroup_uuid="usergroup_access_fixture"))
            await db.flush()
            db.add(UserGroupResource(usergroup_id=30, org_id=1, resource_uuid="course_fixture_10"))

    async def test_configuration_works_without_an_extra_activation_flag(self):
        await self.active()
        with patch.dict(os.environ):
            os.environ.pop("ROUTE66_LEARNING_ACCESS_CONFIGURATION_ENABLED", None)
            result = await self.configure()
        self.assertTrue(result["applied"])
        self.assertTrue(await self.decision(1))

    async def test_retired_flag_cannot_disable_ordinary_approved_configuration(self):
        await self.active()
        with patch.dict(os.environ, {"ROUTE66_LEARNING_ACCESS_CONFIGURATION_ENABLED": "false"}):
            self.assertTrue((await self.configure())["applied"])

    async def test_native_plan_failure_releases_owned_access_not_the_roster(self):
        await self.active(); await self.configure()
        async with self.sessions.begin() as db:
            db.add(UserGroupUser(usergroup_id=30, org_id=1, user_id=2, creation_date="manual", update_date="manual"))
        with patch("src.route66_ext.adapters.native_learning_access.check_org_plan", new=AsyncMock(side_effect=HTTPException(403, "Synthetic plan loss"))):
            await self.snapshot("6900000001")
        self.assertEqual([m.user_id for m in await self.members()], [2])
        async with self.sessions() as db:
            pending = await access._events(db, "learning_access_pending", 10)
            self.assertEqual(len(pending), 1)
            self.assertEqual((await db.exec(select(AcademicRosterEntry))).one().status, "active")

    async def test_verified_google_login_succeeds_when_native_plan_temporarily_fails(self):
        from dataclasses import replace
        await self.link()
        proof = replace(self.google, verified_email="6900000001@nrru.ac.th", hosted_domain="nrru.ac.th")
        await self.login(proof); await self.snapshot("6900000001"); await self.configure()
        with patch("src.route66_ext.adapters.native_learning_access.check_org_plan", new=AsyncMock(side_effect=HTTPException(403, "Synthetic plan loss"))):
            user_id, result = await self.login(proof)
        self.assertEqual(user_id, 1); self.assertTrue(result.access_token)
        self.assertEqual(await self.members(), [])

    async def test_automatic_provision_and_explicit_recovery_keep_manual_group_members(self):
        await self.active()
        async with self.sessions.begin() as db:
            cls = await db.get(AcademicClass, 20)
            p = await access.preview(db, 3, cls, 1)
            self.assertTrue(p["will_create_group"])
            await access.apply(db, 3, cls, 1, expected_fingerprint=p["expected_fingerprint"],
                request_id=uuid.uuid4().hex, reason="Synthetic reviewed group provisioning")
            binding = await access._binding(db, 10); old_group = binding["group_id"]
            db.add(UserGroupUser(usergroup_id=old_group, org_id=1, user_id=2, creation_date="manual", update_date="manual"))
        async with self.sessions.begin() as db:
            cls = await db.get(AcademicClass, 20)
            p = await access.preview(db, 3, cls, 1, replace_group=True)
            await access.apply(db, 3, cls, 1, replace_group=True, expected_fingerprint=p["expected_fingerprint"],
                request_id=uuid.uuid4().hex, reason="Synthetic explicit recovery")
            self.assertNotEqual((await access._binding(db, 10))["group_id"], old_group)
        self.assertEqual([m.user_id for m in await self.members(old_group)], [2])
        self.assertTrue(await self.decision(1))

    async def test_deleted_group_recovers_with_new_identity_without_losing_progress(self):
        await self.active(); await self.configure()
        async with self.sessions.begin() as db:
            await db.delete(await db.get(UserGroup, 30))
        await self.claim()
        async with self.sessions.begin() as db:
            cls = await db.get(AcademicClass, 20)
            p = await access.preview(db, 3, cls, 1, replace_group=True)
            await access.apply(db, 3, cls, 1, replace_group=True, expected_fingerprint=p["expected_fingerprint"],
                request_id=uuid.uuid4().hex, reason="Synthetic deleted-group repair")
        self.assertTrue(await self.decision(1))

    async def configure(self, enabled=True, request_id=None, expected=None, group_id=30):
        async with self.sessions.begin() as db:
            cls = await db.get(AcademicClass, 20)
            preview = await access.preview(db, 3, cls, 1, group_id, enabled)
            return await access.apply(db, 3, cls, 1, group_id=group_id, enabled=enabled,
                expected_fingerprint=expected or preview["expected_fingerprint"],
                request_id=request_id or uuid.uuid4().hex, reason="Synthetic reviewed native access")

    async def active(self):
        await self.claim()
        await self.snapshot("6900000001")

    async def members(self, group=30):
        async with self.sessions() as db:
            return (await db.exec(select(UserGroupUser).where(UserGroupUser.usergroup_id == group))).all()

    async def decision(self, user_id, action=AccessAction.READ):
        request = Request({"type": "http", "method": "GET", "path": "/api/v1/courses/course_fixture_10",
                           "headers": [], "query_string": b""})
        async with self.sessions() as db:
            actor = AnonymousUser() if user_id == 0 else PublicUser.model_validate(await db.get(User, user_id))
            result = await check_resource_access(request, db, actor, "course_fixture_10", action,
                                                  raise_on_deny=False)
            return result.allowed

    async def test_group_org_drift_releases_original_owned_rows_not_new_org_members(self):
        from src.route66_ext.adapters.db_organizations import Organization
        await self.active(); await self.configure()
        async with self.sessions.begin() as db:
            db.add(Organization(id=2, name="Synthetic other org", slug="synthetic2", email="fixture2@example.com", org_uuid="org_fixture2"))
            await db.flush()
            group = await db.get(UserGroup, 30); group.org_id = 2; db.add(group)
            db.add(UserGroupUser(usergroup_id=30, org_id=2, user_id=2, creation_date="manual", update_date="manual"))
        await self.claim()
        self.assertEqual([m.user_id for m in await self.members()], [2])
        self.assertFalse(await self.decision(1))

    async def test_recovery_never_adopts_a_receipt_without_its_authorization(self):
        await self.active(); await self.configure()
        async with self.sessions.begin() as db:
            manual = UserGroupUser(usergroup_id=30, org_id=1, user_id=2, creation_date="manual", update_date="manual")
            db.add(manual); await db.flush()
            db.add(AcademicClassEvent(actor_user_id=3, kind=access._MEMBER, details={"course_id": 10,
                "group_id": 30, "membership": {"id": manual.id, "user_id": 2, "creation_date": "manual", "action": "added"}}))
        await self.claim()
        self.assertEqual([m.user_id for m in await self.members()], [2])
        async with self.sessions() as db:
            self.assertTrue(await access._events(db, "learning_access_pending", 10))

    async def test_private_course_handoff_uses_native_read_not_public_visibility(self):
        await self.active()
        from src.route66_ext.services.academic_projection import project
        from src.route66_ext.db.school_identity import SchoolGoogleEvidence
        req = Request({"type": "http", "method": "GET", "path": "/api/v1/academic-classes", "headers": [], "query_string": b""})
        async def available():
            async with self.sessions() as db:
                user = PublicUser.model_validate(await db.get(User, 1))
                proof = (await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id == 1))).one()
                return (await project(db, user, 1, proof, request=req))["classes"][0]["course_available"]
        self.assertFalse(await available()); await self.configure(); self.assertTrue(await available())

    async def test_explicit_teacher_read_is_not_authorship_and_revokes_with_assignment(self):
        from dataclasses import replace
        from src.route66_ext.db.academic_classes import TeachingAssignment
        proof = replace(self.google, subject="synthetic-teacher", verified_email="fixture.teacher@nrru.ac.th", hosted_domain="nrru.ac.th")
        await self.link(user=2, proof=proof); await self.login(proof)
        await self.configure()
        self.assertTrue(await self.decision(2)); self.assertFalse(await self.decision(2, AccessAction.UPDATE))
        async with self.sessions.begin() as db:
            assignment = (await db.exec(select(TeachingAssignment))).one()
            assignment.active = False; db.add(assignment); await db.flush()
            await access.refresh_course(db, 3, 10)
        self.assertFalse(await self.decision(2))

    async def test_native_teacher_request_admin_connection_and_idempotent_private_access(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from contextlib import asynccontextmanager
        from fastapi import FastAPI
        import httpx
        from src.route66_ext.routers import academic_classes as api, school_identity, class_connections as connections
        from src.route66_ext.db.school_identity import NrruTeacherIdentity
        teacher = replace(self.google, subject="synthetic-requesting-teacher", verified_email="fixture.teacher@nrru.ac.th", hosted_domain="nrru.ac.th")
        identity_id = await self.link(user=2, proof=teacher); _, teacher_session = await self.login(teacher)
        async with self.sessions.begin() as db:
            db.add(NrruTeacherIdentity(user_id=2, identity_id=identity_id, officer_id="90001", officer_code="90002", name_th="ผู้สอนทดสอบ", name_en="Synthetic teacher"))
        admin = replace(self.google, subject="synthetic-connecting-admin", verified_email="fixture-admin@example.com")
        await self.link(user=3, proof=admin); _, admin_session = await self.login(admin)
        config = SimpleNamespace(org_id=1, handoff=SimpleNamespace(client=SimpleNamespace(public_origin="https://learn.example.com")))
        app = FastAPI(); app.include_router(api.router, prefix="/api/v1/academic-classes")
        async def database():
            async with self.sessions() as db: yield db
        app.dependency_overrides[get_db_session] = database
        @asynccontextmanager
        async def source_resources(_): yield None, None
        timetable = {"academic_year": 2569, "semester": 2, "classes": [{"registry_course_id": "100", "section": "P2", "course_code": "990001", "title": "Synthetic official course"}]}
        imported_rows = self.rows("6900000001")
        source_fetch = AsyncMock(return_value=(imported_rows, "b" * 64))
        with patch.object(school_identity, "settings", return_value=config), patch.object(connections, "resources", source_resources), patch.object(connections, "throttle", AsyncMock()), patch.object(connections, "teacher_timetable", AsyncMock(return_value=timetable)), patch.object(connections.roster, "fetch_roster", source_fetch):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://learn.example.com", headers={"Origin": "https://learn.example.com"}, cookies={"LH_access": teacher_session.access_token}) as learner:
                path = "/api/v1/academic-classes/connections/requests"
                body = {"registry_course_id": "100", "academic_year": 2569, "semester": 2, "section": "P2"}
                denied = await learner.post(path, json=body, headers={"Origin": "https://foreign.invalid"})
                self.assertEqual(denied.status_code, 403)
                sent = await learner.post(path, json=body); self.assertEqual(sent.status_code, 200, sent.text)
                ident = sent.json()["id"]; self.assertEqual((await learner.post(path, json=body)).json()["id"], ident)
                self.assertEqual((await learner.post(f"{path}/{ident}/preview", json={"course_id": 10})).status_code, 403)
                self.assertFalse(await self.decision(2))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://learn.example.com", headers={"Origin": "https://learn.example.com"}, cookies={"LH_access": admin_session.access_token}) as owner:
                self.assertEqual(len((await owner.get(path)).json()["requests"]), 1)
                p = await owner.post(f"{path}/{ident}/preview", json={"course_id": 10})
                self.assertEqual(p.status_code, 200, p.text)
                self.assertNotIn("rows", p.json()); self.assertNotIn("students", p.json())
                self.assertEqual((p.json()["candidate_count"], p.json()["source_kind"], p.json()["source_digest"]), (0, "course_rtf", "b" * 64))
                apply_body = {"course_id": 10, "confirm_changes": True, "expected_fingerprint": p.json()["expected_fingerprint"], "request_id": uuid.uuid4().hex}
                rejected = await owner.post(f"{path}/{ident}/connect", json={**apply_body, "confirm_changes": False})
                self.assertEqual(rejected.status_code, 400)

                source_fetch.side_effect = ValueError("Synthetic registrar outage")
                unavailable = await owner.post(f"{path}/{ident}/connect", json=apply_body)
                self.assertEqual(unavailable.status_code, 503)
                self.assertFalse(await self.decision(2))
                async with self.sessions() as db:
                    self.assertEqual(len((await db.exec(select(AcademicClass))).all()), 1)
                    self.assertEqual((await db.exec(select(AcademicRosterEntry))).all(), [])

                source_fetch.side_effect = None
                source_fetch.return_value = (imported_rows, "c" * 64)
                changed = await owner.post(f"{path}/{ident}/connect", json=apply_body)
                self.assertEqual(changed.status_code, 409)
                self.assertFalse(await self.decision(2))
                async with self.sessions() as db:
                    self.assertEqual(len((await db.exec(select(AcademicClass))).all()), 1)
                    self.assertEqual((await db.exec(select(AcademicRosterEntry))).all(), [])

                source_fetch.return_value = (imported_rows, "b" * 64)
                connected = await owner.post(f"{path}/{ident}/connect", json=apply_body)
                self.assertEqual(connected.status_code, 200, connected.text)
                self.assertTrue(connected.json()["roster_imported"])
                fetches_after_connect = source_fetch.await_count
                replay = await owner.post(f"{path}/{ident}/connect", json=apply_body)
                self.assertEqual(replay.json()["class_id"], connected.json()["class_id"])
                self.assertEqual(source_fetch.await_count, fetches_after_connect)
        self.assertTrue(await self.decision(2)); self.assertFalse(await self.decision(2, AccessAction.UPDATE))
        async with self.sessions() as db:
            self.assertEqual(len((await db.exec(select(AcademicClass))).all()), 2)
            imported = (await db.exec(select(AcademicRosterEntry).join(AcademicClass).where(AcademicClass.section == "P2"))).all()
            self.assertEqual(len(imported), 1)
            created = (await db.exec(select(AcademicClass).where(AcademicClass.section == "P2"))).one()
            self.assertIsNone(created.registry_class_id)
            self.assertEqual((await db.exec(select(ResourceAuthor))).all(), [])
            self.assertEqual((await db.exec(select(Trail))).all(), [])
            self.assertEqual((await db.exec(select(TrailRun))).all(), [])
            self.assertEqual((await db.exec(select(TrailStep))).all(), [])
            teacher_user = await db.get(User, 2)
            self.assertFalse(teacher_user.is_superadmin)
            rows = (await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind == "class_connection_completed"))).all()
            self.assertEqual(len(rows), 1); self.assertEqual(rows[0].actor_user_id, 3)
            snapshots = (await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind == "roster_snapshot_applied", AcademicClassEvent.class_id == created.id))).all()
            self.assertEqual(len(snapshots), 1)
            self.assertEqual((snapshots[0].details["source_kind"], snapshots[0].details["source_hash"]), ("course_rtf", "b" * 64))

    async def test_assigned_teacher_section_setup_and_persisted_request_status(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from contextlib import asynccontextmanager
        from fastapi import FastAPI
        import httpx
        from src.route66_ext.routers import academic_classes as api, school_identity, class_connections as connections
        from src.route66_ext.db.school_identity import NrruTeacherIdentity
        from src.route66_ext.db.academic_classes import TeachingAssignment
        proof = replace(self.google, subject="synthetic-direct-teacher", verified_email="direct.teacher@nrru.ac.th", hosted_domain="nrru.ac.th")
        identity = await self.link(user=2, proof=proof); _, session = await self.login(proof)
        async with self.sessions.begin() as db:
            db.add(NrruTeacherIdentity(user_id=2, identity_id=identity, officer_id="90001", officer_code="90002", name_th="ผู้สอนทดสอบ", name_en="Synthetic teacher"))
            assignment = (await db.exec(select(TeachingAssignment).where(TeachingAssignment.user_id == 2))).one()
            assignment.active = False; db.add(assignment)
        app = FastAPI(); app.include_router(api.router, prefix="/api/v1/academic-classes")
        async def database():
            async with self.sessions() as db: yield db
        app.dependency_overrides[get_db_session] = database
        config = SimpleNamespace(org_id=1, handoff=SimpleNamespace(client=SimpleNamespace(public_origin="https://learn.example.com")))
        @asynccontextmanager
        async def resources(_): yield None, None
        facts = {"registry_course_id": "100", "academic_year": 2569, "semester": 2, "section": "P2"}
        timetable = {**facts, "classes": [{"registry_course_id": "100", "section": "P2", "course_code": "990001", "title": "Synthetic subject"}]}
        fetch = AsyncMock(return_value=(self.rows("6900000001"), "d" * 64))
        with patch.object(school_identity, "settings", return_value=config), patch.object(connections, "resources", resources), patch.object(connections, "throttle", AsyncMock()), patch.object(connections, "teacher_timetable", AsyncMock(return_value=timetable)), patch.object(connections.roster, "fetch_roster", fetch):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://learn.example.com", headers={"Origin": "https://learn.example.com"}, cookies={"LH_access": session.access_token}) as client:
                base = "/api/v1/academic-classes/connections"
                status = await client.get(base + "/section", params=facts)
                self.assertEqual(status.status_code, 200, status.text)
                self.assertEqual(status.json()["status"], "needs_course")
                self.assertIn("no-store", status.headers["cache-control"])
                request = await client.post(base + "/requests", json=facts)
                self.assertEqual(request.status_code, 200, request.text)
                status = (await client.get(base + "/section", params=facts)).json()
                self.assertEqual((status["status"], status["request_id"]), ("requested", request.json()["id"]))
                self.assertEqual(fetch.await_count, 0)
                denied = await client.post(base + "/setup", json={**facts, "course_id": 10})
                self.assertEqual(denied.status_code, 403)
                async with self.sessions.begin() as db:
                    assignment = (await db.exec(select(TeachingAssignment).where(TeachingAssignment.user_id == 2))).one()
                    assignment.active = True; db.add(assignment)
                status = (await client.get(base + "/section", params=facts)).json()
                self.assertEqual(status["status"], "ready"); self.assertEqual([c["id"] for c in status["courses"]], [10])
                self.assertEqual((await client.post(base + "/setup", json={**facts, "course_id": 11})).status_code, 403)
                self.assertEqual((await client.post(base + "/setup", json={**facts, "course_id": 10}, headers={"Origin": "https://foreign.invalid"})).status_code, 403)
                self.assertEqual((await client.post(base + "/setup", json={**facts, "section": "P99", "course_id": 10})).status_code, 409)
                fetch.side_effect = ValueError("Synthetic outage")
                self.assertEqual((await client.post(base + "/setup", json={**facts, "course_id": 10})).status_code, 503)
                async with self.sessions() as db:
                    self.assertEqual(len((await db.exec(select(AcademicClass))).all()), 1)
                    self.assertEqual((await db.exec(select(AcademicRosterEntry))).all(), [])
                fetch.side_effect = None
                ready = await client.post(base + "/setup", json={**facts, "course_id": 10})
                self.assertEqual(ready.status_code, 200, ready.text)
                self.assertEqual(ready.json()["roster_count"], 1)
                fetches = fetch.await_count
                self.assertEqual((await client.post(base + "/setup", json={**facts, "course_id": 10})).json()["class_id"], ready.json()["class_id"])
                self.assertEqual((await client.get(base + "/section", params=facts)).json()["status"], "connected")
                self.assertEqual(fetch.await_count, fetches)
                async with self.sessions.begin() as db:
                    assignment = (await db.exec(select(TeachingAssignment).where(TeachingAssignment.user_id == 2))).one()
                    assignment.active = False; db.add(assignment)
                self.assertEqual((await client.post(base + "/setup", json={**facts, "course_id": 10})).status_code, 403)
        async with self.sessions() as db:
            self.assertEqual(len((await db.exec(select(AcademicRosterEntry))).all()), 1)
            self.assertEqual(len((await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind == "class_connection_completed"))).all()), 1)
            self.assertFalse((await db.get(User, 2)).is_superadmin)
            self.assertEqual((await db.exec(select(UserGroupUser))).all(), [])
            self.assertEqual((await db.exec(select(ResourceAuthor))).all(), [])
            self.assertEqual((await db.exec(select(TrailRun))).all(), [])

    async def test_official_roster_reads_own_section_without_learning_assignment_or_writes(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from contextlib import asynccontextmanager
        from fastapi import FastAPI
        import httpx
        from src.route66_ext.routers import academic_classes as api, school_identity, class_connections as connections
        from src.route66_ext.db.school_identity import NrruTeacherIdentity
        from src.route66_ext.db.academic_classes import TeachingAssignment
        proof = replace(self.google, subject="official-reader", verified_email="official.reader@nrru.ac.th", hosted_domain="nrru.ac.th")
        identity = await self.link(user=2, proof=proof); _, session = await self.login(proof)
        async with self.sessions.begin() as db:
            db.add(NrruTeacherIdentity(user_id=2, identity_id=identity, officer_id="90001", officer_code="90002", name_th="ผู้สอนทดสอบ", name_en="Synthetic teacher"))
            assignment = (await db.exec(select(TeachingAssignment).where(TeachingAssignment.user_id == 2))).one()
            assignment.active = False; db.add(assignment)
        app = FastAPI(); app.include_router(api.router, prefix="/api/v1/academic-classes")
        async def database():
            async with self.sessions() as db: yield db
        app.dependency_overrides[get_db_session] = database
        config = SimpleNamespace(org_id=1, handoff=SimpleNamespace(client=SimpleNamespace(public_origin="https://learn.example.com")))
        @asynccontextmanager
        async def resources(_): yield None, None
        facts = {"registry_course_id": "100", "academic_year": 2569, "semester": 2, "section": "P2"}
        timetable = {**facts, "classes": [{"registry_course_id": "100", "section": "P2", "course_code": "990001", "title": "Synthetic subject"}]}
        models = (AcademicClass, AcademicRosterEntry, AcademicClassEvent, SchoolStudent, UserGroupUser, ResourceAuthor, TrailRun)
        async def snapshot():
            async with self.sessions() as db:
                return {model.__name__: [r.model_dump(mode="json") for r in (await db.exec(select(model))).all()] for model in models}
        before = await snapshot()
        fetch = AsyncMock(return_value=(self.rows("6900000001"), "d" * 64))
        with patch.object(school_identity, "settings", return_value=config), patch.object(connections, "resources", resources), patch.object(connections, "throttle", AsyncMock()), patch.object(connections, "teacher_timetable", AsyncMock(return_value=timetable)), patch.object(connections.roster, "fetch_roster", fetch):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://learn.example.com", cookies={"LH_access": session.access_token}) as client:
                path = "/api/v1/academic-classes/connections/official-roster"
                result = await client.get(path, params=facts)
                self.assertEqual(result.status_code, 200, result.text)
                self.assertIn("no-store", result.headers["cache-control"])
                self.assertIn("Cookie", result.headers["vary"])
                self.assertEqual(result.json()["students"][0]["student_number"], "6900000001")
                self.assertNotIn("user_id", result.json()["students"][0])
                cls = fetch.await_args.args[0]
                self.assertEqual((cls.registry_class_id, cls.registry_course_code, cls.section), (None, "990001", "P2"))
                self.assertEqual((await client.get(path, params={**facts, "section": "P99"})).status_code, 409)
                self.assertEqual(fetch.await_count, 1)
                fetch.side_effect = ValueError("Synthetic source outage")
                self.assertEqual((await client.get(path, params=facts)).status_code, 503)
                fetch.side_effect = None
                async with self.sessions.begin() as db:
                    await db.delete(await db.get(NrruTeacherIdentity, 2))
                self.assertEqual((await client.get(path, params=facts)).status_code, 403)
                self.assertEqual(fetch.await_count, 2)
                self.assertEqual((await client.get(path, params=facts, headers={"Cookie": ""})).status_code, 401)
        self.assertEqual(before, await snapshot())

    async def test_connection_dto_rejects_pasted_urls_and_source_is_fixed(self):
        from pydantic import ValidationError
        from types import SimpleNamespace
        from src.route66_ext.routers.class_connections import Section, Choice
        facts = dict(registry_course_id="100", academic_year=2569, semester=2, section="2")
        with self.assertRaises(ValidationError):
            Section.model_validate({**facts, "roster_url": "https://elsewhere.invalid/roster"})
        with self.assertRaises(ValidationError):
            Choice.model_validate({"course_id": 10, "roster_url": "https://reg.nrru.ac.th/"})
        cls = SimpleNamespace(**facts, registry_course_code="990001", registry_class_id=None)
        self.assertEqual(roster.source_url(cls),
            "https://reg.nrru.ac.th/registrar/teach_stdlistRTFallgroup.asp?courseid=100&acadyear=2569&semester=2")
        for section in ("P2", "01"):
            cls.section = section
            self.assertIn("teach_stdlistRTFallgroup.asp?", roster.source_url(cls))
        for section in ("", "../../bad", "<script>"):
            cls.section = section
            with self.assertRaises(ValueError): roster.source_url(cls)

    async def test_native_private_read_is_granted_only_to_matching_student(self):
        await self.active()
        self.assertFalse(await self.decision(1))
        result = await self.configure()
        self.assertEqual(result["added_count"], 1)
        self.assertFalse(result["native_enrollment_changed"])
        self.assertTrue(await self.decision(1))
        self.assertFalse(await self.decision(1, AccessAction.UPDATE))
        self.assertFalse(await self.decision(1, AccessAction.DELETE))
        self.assertFalse(await self.decision(2))
        self.assertFalse(await self.decision(0))

    async def test_login_first_and_roster_first_both_refresh_configured_access(self):
        await self.configure()
        await self.snapshot("6900000001")
        self.assertEqual(await self.members(), [])
        await self.claim()
        self.assertEqual([row.user_id for row in await self.members()], [1])

    async def test_google_first_import_refreshes_access(self):
        await self.configure()
        await self.claim()
        await self.snapshot("6900000001")
        self.assertEqual([row.user_id for row in await self.members()], [1])

    async def test_two_accepted_missing_snapshots_revoke_only_owned_read_grant(self):
        await self.active(); await self.configure()
        await self.snapshot("6900000002")
        self.assertTrue(await self.decision(1))
        await self.snapshot("6900000002")
        self.assertEqual(await self.members(), [])
        self.assertFalse(await self.decision(1))

    async def test_another_active_section_preserves_access(self):
        await self.active(); await self.configure()
        async with self.sessions.begin() as db:
            profile = (await db.exec(select(SchoolStudent))).one()
            db.add(AcademicClass(id=21, course_id=10, academic_year=2569, semester=2, section="P2",
                registry_course_id="100", registry_class_id="201", registry_course_code="990001"))
            await db.flush()
            db.add(AcademicRosterEntry(class_id=21, student_id=profile.id, source="registry", display_position=1))
        await self.snapshot("6900000002"); await self.snapshot("6900000002")
        self.assertTrue(await self.decision(1))

    async def test_conflicting_verified_claims_remove_owned_membership_without_merge(self):
        from src.route66_ext.db.academic_classes import TeachingAssignment
        async with self.sessions.begin() as db:
            # This case exercises two students, not the fixture's independent
            # explicit teacher entitlement (which is tested separately).
            assignment = (await db.exec(select(TeachingAssignment))).one()
            assignment.active = False; db.add(assignment)
        await self.active(); await self.configure(); await self.claim(user=2)
        self.assertEqual(await self.members(), [])
        async with self.sessions() as db:
            self.assertEqual((await db.exec(select(SchoolStudent))).one().user_id, 1)

    async def test_existing_native_memberships_are_not_adopted_or_removed(self):
        await self.configure()
        async with self.sessions.begin() as db:
            db.add(UserGroupUser(usergroup_id=30, org_id=1, user_id=2, creation_date="manual", update_date="manual"))
        await self.active(); await self.configure(enabled=False)
        self.assertEqual([row.user_id for row in await self.members()], [2])

    async def test_first_configuration_cannot_take_over_populated_group(self):
        async with self.sessions.begin() as db:
            db.add(UserGroupUser(usergroup_id=30, org_id=1, user_id=2, creation_date="manual", update_date="manual"))
        with self.assertRaises(HTTPException) as raised:
            await self.configure()
        self.assertEqual(raised.exception.status_code, 409)

    async def test_replacement_native_member_row_is_preserved_as_manual(self):
        await self.active(); await self.configure()
        async with self.sessions.begin() as db:
            old = (await db.exec(select(UserGroupUser))).one()
            await db.delete(old); await db.flush()
            db.add(UserGroupUser(usergroup_id=30, org_id=1, user_id=1, creation_date="replacement", update_date="replacement"))
        await self.configure(enabled=False)
        self.assertEqual([row.creation_date for row in await self.members()], ["replacement"])

    async def test_group_linked_to_another_resource_fails_closed(self):
        async with self.sessions.begin() as db:
            db.add(UserGroupResource(usergroup_id=30, org_id=1, resource_uuid="course_fixture_11"))
        with self.assertRaises(HTTPException) as raised:
            await self.configure()
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(await self.members(), [])

    async def test_duplicate_native_course_uuid_cannot_alias_distinct_course_ids(self):
        async with self.sessions.begin() as db:
            other = await db.get(Course, 11); other.course_uuid = "course_fixture_10"; db.add(other)
        with self.assertRaises(HTTPException) as raised:
            await self.configure()
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(await self.members(), [])

    async def test_duplicate_native_group_uuid_is_ambiguous(self):
        async with self.sessions.begin() as db:
            db.add(UserGroup(id=31, org_id=1, name="Ambiguous native fixture", description="Fixture",
                usergroup_uuid="usergroup_access_fixture"))
        with self.assertRaises(HTTPException) as raised:
            await self.configure()
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(await self.members(), [])

    async def test_missing_group_or_wrong_org_is_not_created(self):
        with self.assertRaises(HTTPException) as raised:
            await self.configure(group_id=999)
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(await self.members(), [])

    async def test_teacher_cannot_enable_native_access(self):
        async with self.sessions() as db:
            with self.assertRaises(HTTPException) as raised:
                await access.preview(db, 2, await db.get(AcademicClass, 20), 1, 30)
            self.assertEqual(raised.exception.status_code, 403)

    async def test_stale_preview_rejects_without_grants_or_receipts(self):
        await self.active()
        with self.assertRaises(HTTPException) as raised:
            await self.configure(expected="0" * 64)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(await self.members(), [])
        async with self.sessions() as db:
            self.assertEqual(await access._events(db, access._CONFIG), [])

    async def test_malformed_configuration_requires_review_before_any_native_write(self):
        async with self.sessions.begin() as db:
            db.add(AcademicClassEvent(actor_user_id=3, class_id=20, kind=access._CONFIG,
                details={"course_id": 10, "group_id": 30, "enabled": "true"}))
        with self.assertRaises(HTTPException) as raised:
            await self.configure()
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(await self.members(), [])

    async def test_event_class_and_course_provenance_must_agree(self):
        async with self.sessions.begin() as db:
            db.add(AcademicClassEvent(actor_user_id=3, class_id=20, kind=access._CONFIG,
                details={"course_id": 11, "org_id": 1, "group_id": 30,
                         "group_uuid": "usergroup_access_fixture", "enabled": True,
                         "reason": "Synthetic inconsistent evidence"}))
        with self.assertRaises(HTTPException) as raised:
            await self.configure()
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(await self.members(), [])

    async def test_malformed_membership_provenance_cannot_be_ignored(self):
        await self.active(); await self.configure()
        async with self.sessions.begin() as db:
            db.add(AcademicClassEvent(actor_user_id=3, kind=access._MEMBER,
                details={"course_id": 10, "group_id": 30, "membership": {"action": "unexpected"}}))
        with self.assertRaises(HTTPException) as raised:
            await self.configure(enabled=False)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(len(await self.members()), 1)

    async def test_request_replay_is_idempotent_and_body_collision_rejected(self):
        await self.active()
        request_id = uuid.uuid4().hex
        async with self.sessions.begin() as db:
            cls = await db.get(AcademicClass, 20)
            fingerprint = (await access.preview(db, 3, cls, 1, 30))["expected_fingerprint"]
            args = dict(group_id=30, enabled=True, expected_fingerprint=fingerprint,
                        request_id=request_id, reason="Synthetic reviewed access")
            self.assertFalse((await access.apply(db, 3, cls, 1, **args))["replayed"])
        async with self.sessions.begin() as db:
            cls = await db.get(AcademicClass, 20)
            self.assertTrue((await access.apply(db, 3, cls, 1, **args))["replayed"])
            with self.assertRaises(HTTPException):
                await access.apply(db, 3, cls, 1, **{**args, "enabled": False})
        self.assertEqual(len(await self.members()), 1)

    async def test_parallel_identical_apply_is_exactly_once(self):
        import asyncio
        await self.active()
        async with self.sessions.begin() as db:
            fingerprint = (await access.preview(db, 3, await db.get(AcademicClass, 20), 1, 30))["expected_fingerprint"]
        request_id = uuid.uuid4().hex
        async def run():
            async with self.sessions.begin() as db:
                return await access.apply(db, 3, await db.get(AcademicClass, 20), 1,
                    group_id=30, enabled=True, expected_fingerprint=fingerprint,
                    request_id=request_id, reason="Synthetic concurrent reviewed access")
        results = await asyncio.gather(run(), run())
        self.assertEqual(sorted(row["replayed"] for row in results), [False, True])
        self.assertEqual(len(await self.members()), 1)

    async def test_unpublished_course_never_exposes_drafts(self):
        await self.active()
        async with self.sessions.begin() as db:
            course = await db.get(Course, 10); course.published = False; db.add(course)
        await self.configure()
        self.assertFalse(await self.decision(1))

    async def test_disabled_configuration_does_not_regrant_on_roster_refresh(self):
        await self.active(); await self.configure(); await self.configure(enabled=False)
        await self.snapshot("6900000001")
        self.assertEqual(await self.members(), [])

    async def test_native_plan_denial_cannot_create_grants(self):
        await self.active()
        with patch("src.route66_ext.adapters.native_learning_access.check_org_plan", new=AsyncMock(side_effect=HTTPException(403, "Synthetic native plan denial"))):
            with self.assertRaises(HTTPException):
                await self.configure()
        self.assertEqual(await self.members(), [])

    async def test_failed_native_write_rolls_back_even_if_caller_catches_and_commits(self):
        await self.active()
        original = access.native.apply_delta
        async def fail(db, org_id, group_id, delta):
            await original(db, org_id, group_id, delta)
            raise RuntimeError("Synthetic post-write failure")
        async with self.sessions.begin() as db:
            cls = await db.get(AcademicClass, 20)
            fingerprint = (await access.preview(db, 3, cls, 1, 30))["expected_fingerprint"]
            with patch.object(access.native, "apply_delta", fail):
                with self.assertRaises(RuntimeError):
                    await access.apply(db, 3, cls, 1, group_id=30, enabled=True,
                        expected_fingerprint=fingerprint, request_id=uuid.uuid4().hex, reason="Synthetic reviewed failure")
        self.assertEqual(await self.members(), [])
        async with self.sessions() as db:
            self.assertEqual(await access._events(db, access._CONFIG), [])

    async def test_learning_progress_and_other_manual_group_are_preserved(self):
        await self.active()
        async with self.sessions.begin() as db:
            trail = Trail(org_id=1, user_id=1, trail_uuid="trail_fixture", creation_date="original", update_date="original")
            db.add(trail); await db.flush()
            run = TrailRun(trail_id=trail.id, course_id=10, org_id=1, user_id=1,
                status=StatusEnum.STATUS_COMPLETED, data={"original": True}, creation_date="original", update_date="original")
            db.add(run); await db.flush()
            activity = Activity(name="Fixture", course_id=10, org_id=1, activity_uuid="activity_fixture",
                activity_type=ActivityTypeEnum.TYPE_CUSTOM, activity_sub_type=ActivitySubTypeEnum.SUBTYPE_CUSTOM)
            db.add(activity); await db.flush()
            step = TrailStep(trail_id=trail.id, trailrun_id=run.id, activity_id=activity.id, course_id=10,
                org_id=1, user_id=1, complete=True, teacher_verified=True, grade="original-grade",
                data={"evidence": "preserved"}, creation_date="original", update_date="original")
            db.add(step)
            db.add(UserGroup(id=31, org_id=1, name="Manual", description="Native manual grant", usergroup_uuid="usergroup_manual"))
            await db.flush()
            db.add(UserGroupResource(usergroup_id=31, org_id=1, resource_uuid="course_fixture_10"))
            db.add(UserGroupUser(usergroup_id=31, org_id=1, user_id=1, creation_date="manual", update_date="manual"))
            await db.flush()
            before = [copy.deepcopy(x.model_dump()) for x in (trail, run, step)]
        await self.configure(); await self.configure(enabled=False)
        async with self.sessions() as db:
            after = [(await db.exec(select(model))).one().model_dump() for model in (Trail, TrailRun, TrailStep)]
            self.assertEqual(after, before)
        self.assertTrue(await self.decision(1))
        self.assertEqual(len(await self.members(group=31)), 1)

    async def test_public_course_is_not_silently_made_private(self):
        async with self.sessions.begin() as db:
            course = await db.get(Course, 10); course.public = True; db.add(course)
        with self.assertRaises(HTTPException):
            await self.configure()
        async with self.sessions() as db:
            self.assertTrue((await db.get(Course, 10)).public)

    async def test_native_group_drift_preserves_roster_and_requires_repair(self):
        await self.active(); await self.configure()
        async with self.sessions.begin() as db:
            db.add(UserGroupResource(usergroup_id=30, org_id=1, resource_uuid="course_fixture_11"))
        await self.snapshot("6900000002")
        self.assertEqual(await self.members(), [])
        async with self.sessions() as db:
            entries = (await db.exec(select(AcademicRosterEntry))).all()
            self.assertEqual(len(entries), 2)
            self.assertEqual(max(e.missing_count for e in entries), 1)
            self.assertTrue(await access._events(db, "learning_access_pending", 10))

    async def test_native_admin_session_http_preview_confirm_apply_and_retry(self):
        from dataclasses import replace
        from types import SimpleNamespace
        from fastapi import FastAPI
        import httpx
        from src.route66_ext.routers import academic_classes as api, school_identity
        await self.active()
        proof = replace(self.google, subject="synthetic-access-admin", verified_email="fixture-admin@example.com")
        await self.link(user=3, proof=proof)
        _, session = await self.login(proof)
        config = SimpleNamespace(org_id=1, handoff=SimpleNamespace(client=SimpleNamespace(
            public_origin="https://learn.example.com")))
        app = FastAPI(); app.include_router(api.router, prefix="/api/v1/academic-classes")
        async def database():
            async with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db_session] = database
        path = "/api/v1/academic-classes/20/learning-access"
        with patch.object(school_identity, "settings", return_value=config):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                base_url="https://learn.example.com", cookies={"LH_access": session.access_token},
                headers={"Origin": "https://learn.example.com"}) as client:
                response = await client.get(path + "/preview", params={"group_id": 30})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["add_count"], 1)
                body = {"group_id": 30, "enabled": True, "confirm_changes": True,
                    "expected_fingerprint": response.json()["expected_fingerprint"],
                    "request_id": uuid.uuid4().hex, "reason": "Synthetic native-session reviewed access"}
                self.assertEqual((await client.post(path + "/apply", json=body,
                    headers={"Origin": "https://foreign.invalid"})).status_code, 403)
                self.assertEqual((await client.post(path + "/apply", json={**body, "confirm_changes": False})).status_code, 400)
                self.assertEqual((await client.post(path + "/apply", json={**body, "actor_id": 3})).status_code, 422)
                self.assertEqual((await client.post(path + "/apply", json={**body, "enabled": 1})).status_code, 422)
                self.assertEqual(await self.members(), [])
                result = await client.post(path + "/apply", json=body)
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()["added_count"], 1)
                result = await client.post(path + "/apply", json=body)
                self.assertEqual(result.status_code, 200)
                self.assertTrue(result.json()["replayed"])
        self.assertEqual(len(await self.members()), 1)

    async def test_actual_native_course_http_uses_real_fixture_session_and_feature_guard(self):
        from dataclasses import replace
        from fastapi import FastAPI
        import httpx

        async with self.engine.begin() as conn:
            for model in (Chapter, CourseChapter):
                await conn.run_sync(model.__table__.create)
        await self.link()
        _, session = await self.login(replace(self.google,
            verified_email="6900000001@nrru.ac.th", hosted_domain="nrru.ac.th"))
        await self.snapshot("6900000001")
        app = FastAPI(); app.include_router(native_courses_router(), prefix="/courses")
        async def database():
            async with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db_session] = database
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
            base_url="https://learn.example.com", cookies={"LH_access": session.access_token}) as client:
            path = "/courses/course_fixture_10"
            self.assertEqual((await client.get(path)).status_code, 403)
            await self.configure()
            granted = await client.get(path)
            self.assertEqual(granted.status_code, 200)
            self.assertEqual(granted.json()["course_uuid"], "course_fixture_10")
            metadata = await client.get(path + "/meta")
            self.assertEqual(metadata.status_code, 200)
            self.assertEqual(metadata.json()["course_uuid"], "course_fixture_10")
            self.assertEqual(metadata.json()["chapters"], [])
            async with self.sessions.begin() as db:
                course = await db.get(Course, 10); course.published = False; db.add(course)
            self.assertEqual((await client.get(path)).status_code, 403)
            # Exercise the full page metadata handler, not only its initial
            # DASHBOARD check: the chapter reader retains the publication guard.
            self.assertEqual((await client.get(path + "/meta")).status_code, 403)
            async with self.sessions.begin() as db:
                course = await db.get(Course, 10); course.published = True; db.add(course)
                config = (await db.exec(select(OrganizationConfig))).one()
                await db.delete(config)
            self.assertEqual((await client.get(path)).status_code, 404)
            async with self.sessions.begin() as db:
                db.add(OrganizationConfig(org_id=1, config={"features": {"courses": {"enabled": True}}}))
            await self.configure(enabled=False)
            self.assertEqual((await client.get(path)).status_code, 403)

    async def test_authentication_route_uses_existing_native_context_and_origin_guard(self):
        from fastapi import FastAPI
        import httpx
        from src.route66_ext.routers import learning_access as api
        from types import SimpleNamespace
        app = FastAPI(); app.include_router(api.router)
        async with self.sessions() as db:
            async def session():
                yield db
            async def context(*args):
                return PublicUser.model_validate(await db.get(User, 3)), SimpleNamespace(org_id=1,
                    handoff=SimpleNamespace(client=SimpleNamespace(public_origin="https://fixture.invalid"))), None
            app.dependency_overrides[get_db_session] = session
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://fixture.invalid") as client:
                anonymous = await client.get("/20/learning-access/preview", params={"group_id": 30})
                self.assertEqual(anonymous.status_code, 401)
                with patch.object(api, "context", context):
                    response = await client.get("/20/learning-access/preview", params={"group_id": 30},
                        headers={"Origin": "https://foreign.invalid"})
                    self.assertEqual(response.status_code, 200)
                    self.assertNotIn("access-control-allow-origin", response.headers)
                    self.assertIn("no-store", response.headers["cache-control"])
                    body = {"group_id": 30, "enabled": True, "confirm_changes": False,
                            "expected_fingerprint": response.json()["expected_fingerprint"],
                            "request_id": uuid.uuid4().hex, "reason": "Synthetic route test"}
                    with patch.object(api, "boundary", side_effect=HTTPException(403, "Synthetic origin denial")):
                        self.assertEqual((await client.post("/20/learning-access/apply", json=body)).status_code, 403)
                    with patch.object(api, "boundary", lambda *a: None):
                        self.assertEqual((await client.post("/20/learning-access/apply", json=body)).status_code, 400)
