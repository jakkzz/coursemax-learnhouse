"""Synthetic class/roster parity cases on isolated PostgreSQL, never live people."""
import os,unittest
from dataclasses import replace
from unittest.mock import patch
from types import SimpleNamespace
from fastapi import HTTPException,Response
from sqlalchemy import text
from sqlmodel import select
from src.route66_ext.tests.services.test_native_google_sessions import NativeGoogleTests
from src.route66_ext.db.academic_classes import *
from src.db.courses.courses import Course
from src.db.users import User
from src.db.user_organizations import UserOrganization
from src.route66_ext.db.school_identity import SchoolGoogleEvidence
from src.route66_ext.services import academic_rosters as s
from src.route66_ext.routers import academic_classes as api

@unittest.skipUnless(os.getenv('RUN_IDENTITY_POSTGRES_TESTS')=='1','isolated PostgreSQL required')
class AcademicRosterTests(NativeGoogleTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.sessions.begin() as db:
            for id in (10,11):db.add(Course(id=id,org_id=1,name='Synthetic course '+str(id),course_uuid='course_fixture_'+str(id),public=False,open_to_contributors=False))
            await db.flush();db.add(CourseRegistryBinding(course_id=10,registry_course_id='100',course_code='990001'));db.add(TeachingAssignment(course_id=10,user_id=2))
            db.add(AcademicClass(id=20,course_id=10,academic_year=2569,semester=1,section='P1',registry_course_id='100',registry_class_id='200',registry_course_code='990001'))
            await db.execute(text("SELECT setval(pg_get_serial_sequence('academicclass','id'),20,true)"))
    def rows(self,*numbers):return [{'student_number':n,'full_name_th':'นาย นักศึกษาตัวอย่าง '+n[-2:],'faculty':'คณะตัวอย่าง','program':'สาขาตัวอย่าง','display_position':i+1} for i,n in enumerate(numbers)]
    async def snapshot(self,*numbers):
        async with self.sessions.begin() as db:
            await s.serialize(db);return await s.apply_roster(db,await db.get(AcademicClass,20),self.rows(*numbers),'a'*64,2)
    async def claim(self,user=1,number='6900000001'):
        # Native verified admission, not direct student-profile fabrication.
        proof=replace(self.google,subject='subject-'+str(user),verified_email=number+'@nrru.ac.th',hosted_domain='nrru.ac.th')
        from src.route66_ext.services.auth.google_handoff import VerifiedGoogleHandoff
        from src.route66_ext.services.auth.oauth_transactions import LinkActor
        from src.route66_ext.services.auth.native_google import complete_native_google
        async with self.sessions.begin() as db:
            native=await db.get(User,user);native.email_verified=True;db.add(native);await db.flush()
            await complete_native_google(db,VerifiedGoogleHandoff(proof,'link','/classes',LinkActor(user,'a'*64)),org_id=1)
    async def test_roster_first_then_google_preserves_profile_and_entry_ids(self):
        await self.snapshot('6900000001')
        async with self.sessions() as db:
            p=(await db.exec(select(SchoolStudent))).one();entry=(await db.exec(select(AcademicRosterEntry))).one();ids=(p.id,entry.id)
        await self.claim()
        async with self.sessions() as db:
            p=(await db.exec(select(SchoolStudent))).one();entry=(await db.exec(select(AcademicRosterEntry))).one();self.assertEqual((p.id,entry.id),ids);self.assertEqual(p.user_id,1)
            u=await db.get(User,1);self.assertEqual(u.first_name,'Synthetic');self.assertFalse(u.is_superadmin)
    async def test_google_first_then_roster_matches_without_role_or_profile_rewrite(self):
        await self.claim();counts=await self.snapshot('6900000001');self.assertEqual(counts['matched'],1)
        async with self.sessions() as db:self.assertEqual((await db.exec(select(SchoolStudent))).one().user_id,1)
    async def test_repeated_missing_withdraws_and_reactivation_reuses_entry(self):
        await self.snapshot('6900000001','6900000002')
        async with self.sessions() as db:old=(await db.exec(select(AcademicRosterEntry))).all();old_ids=[e.id for e in old]
        a=await self.snapshot('6900000001');self.assertEqual(a['withdrawn'],0)
        b=await self.snapshot('6900000001');self.assertEqual(b['withdrawn'],1)
        c=await self.snapshot('6900000001','6900000002');self.assertEqual(c['reactivated'],1)
        async with self.sessions() as db:self.assertEqual([e.id for e in (await db.exec(select(AcademicRosterEntry).order_by(AcademicRosterEntry.id))).all()],old_ids)
    async def test_manual_members_survive_registry_absence(self):
        async with self.sessions.begin() as db:
            p=SchoolStudent(user_id=3,full_name_th='Manual fixture',faculty='',program='');db.add(p);await db.flush();db.add(AcademicRosterEntry(class_id=20,student_id=p.id,source='manual',display_position=1))
        await self.snapshot('6900000001');await self.snapshot('6900000001')
        async with self.sessions() as db:
            e=(await db.exec(select(AcademicRosterEntry).where(AcademicRosterEntry.source=='manual'))).one();self.assertEqual((e.status,e.missing_count),('active',0))
    async def test_multiple_verified_claims_never_transfer_identity(self):
        await self.claim();await self.snapshot('6900000001');await self.claim(3)
        async with self.sessions() as db:
            p=(await db.exec(select(SchoolStudent))).one();self.assertEqual(p.user_id,1)
            e=(await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id==1))).one()
            self.assertEqual((await s.own_student(db,1,e))[1],'conflict')
            self.assertTrue((await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind=='identity_conflict'))).all())
    async def test_verified_number_fills_manual_identity_in_place(self):
        async with self.sessions.begin() as db:
            p=SchoolStudent(user_id=1,full_name_th='Manual',faculty='',program='');db.add(p);await db.flush();db.add(AcademicRosterEntry(class_id=20,student_id=p.id,source='manual',display_position=1))
        await self.claim();counts=await self.snapshot('6900000001');self.assertEqual(counts['conflicts'],0)
        async with self.sessions() as db:self.assertEqual(len((await db.exec(select(SchoolStudent))).all()),1);self.assertEqual(len((await db.exec(select(AcademicRosterEntry))).all()),1)
    async def test_existing_manual_and_registry_records_are_not_merged(self):
        async with self.sessions.begin() as db:
            p=SchoolStudent(user_id=1,full_name_th='Manual',faculty='',program='');db.add(p);await db.flush();db.add(AcademicRosterEntry(class_id=20,student_id=p.id,source='manual',display_position=1))
        await self.snapshot('6900000001');await self.claim()
        async with self.sessions() as db:
            profiles=(await db.exec(select(SchoolStudent))).all();self.assertEqual(len(profiles),2)
            self.assertIsNone(next(p for p in profiles if p.student_number=='6900000001').user_id)
            self.assertEqual(len((await db.exec(select(AcademicRosterEntry))).all()),2)
    async def test_changed_number_never_rebinds_existing_student(self):
        await self.claim();await self.snapshot('6900000001');await self.snapshot('6900000001','6900000002')
        # New evidence for same permanent provider subject, not a second identity.
        async with self.sessions.begin() as db:
            await s.serialize(db);e=(await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id==1))).one();e.email='6900000002@nrru.ac.th';db.add(e);await db.flush();await s.reconcile_login(db,1)
        async with self.sessions() as db:
            ps=(await db.exec(select(SchoolStudent).order_by(SchoolStudent.student_number))).all();self.assertEqual([p.user_id for p in ps],[1,None])
    async def test_learner_denied_and_teacher_sees_only_assigned_course(self):
        async with self.sessions() as db:
            cls=await db.get(AcademicClass,20);self.assertEqual((await s.can_manage(db,await db.get(User,2),cls,1)).id,10)
            with self.assertRaises(HTTPException) as e:await s.can_manage(db,await db.get(User,3),cls,1)
            self.assertEqual(e.exception.status_code,403)
            cls.course_id=11
            with self.assertRaises(HTTPException):await s.can_manage(db,await db.get(User,2),cls,1)
    async def test_class_registry_binding_cannot_be_taken_by_another_course(self):
        from sqlalchemy.exc import IntegrityError
        with self.assertRaises(IntegrityError):
            async with self.sessions.begin() as db:
                db.add(AcademicClass(course_id=11,academic_year=2569,semester=1,section='P2',registry_course_id='100',registry_class_id='200',registry_course_code='990001'));await db.flush()
    async def test_events_are_append_only_in_database(self):
        await self.snapshot('6900000001')
        for statement in ('UPDATE academicclassevent SET kind=\'changed\'','DELETE FROM academicclassevent'):
            with self.assertRaises(Exception):
                async with self.sessions.begin() as db:await db.execute(text(statement))
    async def test_nine_digit_hint_does_not_get_padded_or_matched(self):
        await self.claim(number='690000001');await self.snapshot('0690000001')
        async with self.sessions() as db:self.assertIsNone((await db.exec(select(SchoolStudent))).one().user_id)
    async def test_classes_query_is_own_only_and_withdrawal_removes_current_access(self):
        await self.claim();await self.snapshot('6900000001')
        async with self.sessions() as db:
            user=await db.get(User,1);e=(await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id==1))).one()
            async def ctx(*args):return user,SimpleNamespace(org_id=1),e
            with patch.object(api,'context',ctx):self.assertEqual(len((await api.classes(None,Response(),db))['classes']),1)
        await self.snapshot('6900000002');await self.snapshot('6900000002')
        async with self.sessions() as db:
            user=await db.get(User,1);e=(await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id==1))).one()
            async def ctx(*args):return user,SimpleNamespace(org_id=1),e
            with patch.object(api,'context',ctx):self.assertEqual((await api.classes(None,Response(),db))['classes'],[])
    async def endpoint_context(self,db,user_id=2):
        from contextlib import asynccontextmanager
        from unittest.mock import AsyncMock
        user=await db.get(User,user_id)
        async def ctx(*args):return user,SimpleNamespace(org_id=1,deployment='fixture'),None
        store=getattr(self,'preview_store',{});self.preview_store=store
        class Redis:
            async def get(self,key):return store.get(key)
            async def eval(self,script,count,key,raw):
                if store.get(key)!=raw:return 0
                del store[key];return 1
        @asynccontextmanager
        async def resources(*args):yield Redis(),None
        return [patch.object(api,'context',ctx),patch.object(api,'boundary',lambda *args:None),patch.object(api,'resources',resources),patch.object(api,'throttle',AsyncMock())]
    async def test_apply_scope_version_confirmation_and_one_use_are_checked(self):
        import json
        token='a'*43;key='lh:roster:fixture:'+token
        payload={'user_id':2,'org_id':1,'class_id':20,'version':0,'source_hash':'b'*64,'rows':self.rows('6900000001')}
        self.preview_store={key:json.dumps(payload)}
        from contextlib import ExitStack
        async with self.sessions() as db:
            with ExitStack() as stack:
                for p in await self.endpoint_context(db):stack.enter_context(p)
                with self.assertRaises(HTTPException):await api.apply(20,api.Apply(preview_id=token,confirm_changes=False),None,Response(),db)
                self.assertIn(key,self.preview_store)
                self.preview_store[key]=json.dumps({**payload,'version':99})
                with self.assertRaises(HTTPException) as e:await api.apply(20,api.Apply(preview_id=token,confirm_changes=True),None,Response(),db)
                self.assertEqual(e.exception.status_code,409)
                self.preview_store[key]=json.dumps(payload)
                data=await api.apply(20,api.Apply(preview_id=token,confirm_changes=True),None,Response(),db)
                self.assertTrue(data['applied']);self.assertNotIn(key,self.preview_store)
                with self.assertRaises(HTTPException):await api.apply(20,api.Apply(preview_id=token,confirm_changes=True),None,Response(),db)
    async def test_revoked_teacher_cannot_apply_cached_roster(self):
        from contextlib import ExitStack
        async with self.sessions.begin() as db:
            record=(await db.exec(select(TeachingAssignment))).one();record.active=False;db.add(record)
        async with self.sessions() as db:
            with ExitStack() as stack:
                for p in await self.endpoint_context(db):stack.enter_context(p)
                with self.assertRaises(HTTPException) as e:await api.apply(20,api.Apply(preview_id='a'*43,confirm_changes=True),None,Response(),db)
                self.assertEqual(e.exception.status_code,403)
    async def test_admin_assignment_is_explicit_and_does_not_elevate_native_role(self):
        from contextlib import ExitStack
        async with self.sessions.begin() as db:
            actor=await db.get(User,1);actor.is_superadmin=True;db.add(actor)
        async with self.sessions() as db:
            with ExitStack() as stack:
                for p in await self.endpoint_context(db,1):stack.enter_context(p)
                result=await api.assign(api.Assignment(course_id=10,user_id=3,reason='Synthetic approved assignment',registry_course_id='100',course_code='990001'),None,Response(),db)
                self.assertFalse(result['native_roles_changed']);self.assertFalse((await db.get(User,3)).is_superadmin)
                self.assertEqual((await db.exec(select(UserOrganization).where(UserOrganization.user_id==3))).one().role_id,4)
    async def test_teacher_cannot_create_against_unapproved_course_mapping(self):
        from contextlib import ExitStack
        async with self.sessions() as db:
            with ExitStack() as stack:
                for p in await self.endpoint_context(db):stack.enter_context(p)
                with self.assertRaises(HTTPException) as e:await api.create(api.ClassSetup(course_id=10,academic_year=2569,semester=1,section='P2',registry_course_id='999',registry_class_id='201'),None,Response(),db)
                self.assertEqual(e.exception.status_code,409)
    async def test_teacher_cannot_grant_teaching_assignment_or_native_roles(self):
        from contextlib import ExitStack
        async with self.sessions() as db:
            with ExitStack() as stack:
                for p in await self.endpoint_context(db):stack.enter_context(p)
                with self.assertRaises(HTTPException) as e:await api.assign(api.Assignment(course_id=11,user_id=3,reason='Synthetic reason'),None,Response(),db)
                self.assertEqual(e.exception.status_code,403)
    async def test_unused_configuration_can_be_corrected_but_imported_class_cannot(self):
        from contextlib import ExitStack
        body=api.Correction(course_id=10,academic_year=2569,semester=1,section='P1',registry_course_id='100',registry_class_id='201',expected_version=0,reason='Synthetic correction')
        async with self.sessions() as db:
            with ExitStack() as stack:
                for p in await self.endpoint_context(db):stack.enter_context(p)
                self.assertTrue((await api.correct(20,body,None,Response(),db))['saved'])
        await self.snapshot('6900000001')
        async with self.sessions() as db:
            with ExitStack() as stack:
                for p in await self.endpoint_context(db):stack.enter_context(p)
                with self.assertRaises(HTTPException):await api.correct(20,body.model_copy(update={'expected_version':2}),None,Response(),db)
    async def test_school_projection_exposes_only_own_matched_registrar_details(self):
        await self.claim();await self.snapshot('6900000001')
        from src.route66_ext.routers import school_identity
        async with self.sessions() as db:
            user=await db.get(User,1);e=(await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id==1))).one()
            async def ctx(*args):return user,SimpleNamespace(org_id=1),e
            with patch.object(api,'context',ctx),patch.object(school_identity,'context',ctx):data=await school_identity.own_identity(None,Response(),db)
            self.assertEqual(data['student_match_status'],'matched');self.assertEqual(data['student_profile']['program'],'สาขาตัวอย่าง');self.assertEqual(len(data['courses']),1)

class ParserTests(unittest.TestCase):
    cls=SimpleNamespace(academic_year=2569,semester=1,section='P1',registry_course_code='990001')
    def html(self,number='6900000001'):
        return ('<table><tr><td>2569</td><td>P1</td><td>990001</td></tr><tr><th>ลำดับ</th><th>รหัส</th><th>ชื่อ</th><th>สาขา</th><th>สถานะ</th></tr><tr><td>คณะตัวอย่าง</td></tr><tr><td>1</td><td>'+number+'</td><td>นาย ตัวอย่าง</td><td>สาขาตัวอย่าง</td><td>R</td></tr></table>').encode('cp874')
    def test_parse_preserves_exact_official_fields(self):
        row=s.parse_roster(self.html(),self.cls)[0]
        self.assertEqual(row['full_name_th'],'นาย ตัวอย่าง');self.assertEqual(row['program'],'สาขาตัวอย่าง');self.assertEqual(row['registry_status_code'],'R')
    def test_wrong_approved_course_code_is_rejected(self):
        with self.assertRaises(ValueError):s.parse_roster(self.html().replace(b'990001',b'990002'),self.cls)
    def test_campus_course_header_is_not_mistaken_for_student_header(self):
        header='<tr><td>รายวิชา</td><td>รหัสวิชา</td><td>ชื่อวิชา</td><td>990001</td><td>P1</td></tr>'.encode('cp874')
        self.assertEqual(len(s.parse_roster(self.html().replace(b'<table>',b'<table>'+header),self.cls)),1)
    def test_incomplete_number_rejected_not_silently_missing(self):
        with self.assertRaises(ValueError):s.parse_roster(self.html('690000001'),self.cls)
    def test_wrong_year_section_and_duplicates_rejected(self):
        for data in [self.html().replace(b'2569',b'2568'),self.html().replace(b'P1',b'P2'),self.html()+self.html()]:
            with self.assertRaises(ValueError):s.parse_roster(data,self.cls)
    def test_fixed_source_query_never_guesses_student_portal(self):
        cls=SimpleNamespace(registry_class_id='200',registry_course_id='100',academic_year=2569,semester=1)
        self.assertTrue(s.source_url(cls).startswith(s.ROSTER_URL+'?classid=200&courseid=100&acadyear=2569&semester=1'))

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
