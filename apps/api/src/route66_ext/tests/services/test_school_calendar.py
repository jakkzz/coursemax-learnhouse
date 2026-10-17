"""Shared calendars, school-class schedules and attendance on isolated PostgreSQL; synthetic only."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import httpx
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlmodel import select
from src.route66_ext.tests.services.test_academic_rosters import AcademicRosterTests
from src.route66_ext.db.academic_classes import AcademicClass, AcademicRosterEntry, TeachingAssignment
from src.route66_ext.db.class_attendance import AttendanceSession, AttendanceChallenge
from src.route66_ext.db.school_calendar import CALENDAR_TABLES, ClassSchedule, SchoolCalendar, SchoolCalendarRevision, SchoolCalendarSource, SchoolCalendarAttachment
from src.route66_ext.db.school_identity import SchoolGoogleEvidence, NrruTeacherIdentity
from src.db.users import User
from src.db.user_organizations import UserOrganization
from src.route66_ext.routers import school_calendars as api, class_connections as connections, class_attendance as attendance_api
from src.route66_ext.services import academic_rosters as roster, learning_access as access

ORIGIN = 'https://learn.example.com'


def blank_pdf(pages=1):
    from pypdf import PdfWriter
    writer, out = PdfWriter(), BytesIO()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    writer.write(out)
    return out.getvalue()


def monday(offset_weeks):
    today = date.today()
    return today - timedelta(days=today.weekday()) + timedelta(weeks=offset_weeks)


def week(n, start, rotation='teaching', teaching=True):
    return {'number': n, 'starts_on': start.isoformat(), 'ends_on': (start + timedelta(days=6)).isoformat(),
            'rotation': rotation, 'teaching': teaching, 'page': 1}


def calendar_payload(first, count=4, closures=()):
    weeks = [week(i + 1, first + timedelta(weeks=i)) for i in range(count)]
    return {'timezone': 'Asia/Bangkok', 'terms': [{'semester': 1, 'starts_on': first.isoformat(),
        'ends_on': (first + timedelta(weeks=count) - timedelta(days=1)).isoformat(), 'weeks': weeks,
        'closures': list(closures)}]}


MEETINGS = [{'day': 'จันทร์', 'start_time': '9:00', 'end_time': '12:00', 'details': 'ROOM-1'},
            {'day': 'พฤหัสบดี', 'start_time': '13:00', 'end_time': '15:00', 'details': 'LAB-2'}]


class SchoolCalendarTests(AcademicRosterTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.engine.begin() as conn:
            for table in CALENDAR_TABLES:
                await conn.run_sync(table.create)
        self.actor = 1
        self.config = SimpleNamespace(org_id=1, deployment='fixture', handoff=SimpleNamespace(client=SimpleNamespace(public_origin=ORIGIN)))
        self.timetable = {}
        app = FastAPI()
        app.include_router(api.router, prefix='/api/v1/school-calendars')
        app.include_router(connections.router, prefix='/api/v1/academic-classes')
        app.include_router(attendance_api.router, prefix='/api/v1/attendance')

        async def database():
            async with self.sessions() as db:
                yield db

        async def context(request, db):
            user = await db.get(User, self.actor)
            evidence = (await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id == self.actor))).first()
            from src.route66_ext.adapters.native_learning_access_test_support import PublicUser
            return PublicUser.model_validate(user), self.config, evidence

        async def verified(db, user, config, evidence, body, request, meetings=False):
            facts = self.timetable.get((user.id, body.registry_course_id, body.section))
            if facts is None:
                raise HTTPException(409, 'Select one exact section from your current registrar timetable')
            data = {'registry_course_id': body.registry_course_id, 'academic_year': body.academic_year,
                    'semester': body.semester, 'section': body.section, **facts, 'org_id': 1, 'teacher_id': user.id}
            if not meetings:
                data.pop('meetings')
            return data

        app.dependency_overrides[api.get_db_session] = database
        app.dependency_overrides[attendance_api.get_db_session] = database
        self.calendar_patches = [patch.object(api, 'context', context), patch.object(attendance_api, 'context', context),
                                 patch.object(api, 'verified_section', verified), patch.object(connections, 'verified_section', verified),
                                 patch.object(connections, 'context', context), patch.object(connections, 'boundary', lambda *a: None)]
        for p in self.calendar_patches:
            p.start()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN, headers={'Origin': ORIGIN})

    async def asyncTearDown(self):
        await self.client.aclose()
        for p in reversed(self.calendar_patches):
            p.stop()
        await super().asyncTearDown()

    async def make_admin(self, user=1):
        async with self.sessions.begin() as db:
            row = await db.get(User, user); row.is_superadmin = True; db.add(row)

    async def teacher(self, user=3):
        proof = replace(self.google, subject='teacher-' + str(user), verified_email=f'fixture.teacher{"abc"[user - 1]}@nrru.ac.th', hosted_domain='nrru.ac.th')
        from src.route66_ext.services.auth.google_handoff import VerifiedGoogleHandoff
        from src.route66_ext.services.auth.oauth_transactions import LinkActor
        from src.route66_ext.services.auth.native_google import complete_native_google
        async with self.sessions.begin() as db:
            native = await db.get(User, user); native.email_verified = True; db.add(native); await db.flush()
            await complete_native_google(db, VerifiedGoogleHandoff(proof, 'link', '/classes', LinkActor(user, 'a' * 64)), org_id=1)
        async with self.sessions.begin() as db:
            evidence = (await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id == user))).one()
            db.add(NrruTeacherIdentity(user_id=user, identity_id=evidence.identity_id, officer_id=str(90000 + user),
                                       officer_code=str(80000 + user), name_th='ผู้สอนทดสอบ', name_en='Synthetic teacher'))

    async def published(self, payload, track='ภาคปกติ'):
        self.actor = 1
        data = blank_pdf()
        created = await self.client.post('/api/v1/school-calendars', data={'name': 'ปฏิทินทดสอบ', 'academic_year': '2569', 'track': track},
                                         files={'file': ('calendar.pdf', data, 'application/pdf')})
        self.assertEqual(created.status_code, 200, created.text)
        revision = created.json()
        saved = await self.client.put(f"/api/v1/school-calendars/revisions/{revision['id']}", json={'expected_version': 0, 'payload': payload})
        self.assertEqual(saved.status_code, 200, saved.text)
        done = await self.client.post(f"/api/v1/school-calendars/revisions/{revision['id']}/publish", json={'expected_version': 1, 'reviewed': True})
        self.assertEqual(done.status_code, 200, done.text)
        return done.json()

    def section(self, section='P9', course='100'):
        return {'registry_course_id': course, 'academic_year': 2569, 'semester': 1, 'section': section}

    async def preview(self, revision_id, section, pattern='onsite'):
        response = await self.client.post('/api/v1/school-calendars/schedules/preview',
                                          json={'section': section, 'revision_id': revision_id, 'pattern': pattern})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def apply(self, revision_id, section, preview, pattern='onsite'):
        return await self.client.post('/api/v1/school-calendars/schedules/apply', json={
            'section': section, 'revision_id': revision_id, 'pattern': pattern,
            'expected_version': preview['version'], 'fingerprint': preview['fingerprint'], 'reviewed': True})

    async def test_source_crud_review_publish_and_administrator_authority(self):
        await self.make_admin()
        self.actor = 3
        denied = await self.client.post('/api/v1/school-calendars', data={'name': 'x', 'academic_year': '2569', 'track': 'regular'},
                                        files={'file': ('c.pdf', blank_pdf(), 'application/pdf')})
        self.assertEqual(denied.status_code, 403)
        self.actor = 1
        data = blank_pdf()
        bad = await self.client.post('/api/v1/school-calendars', data={'name': 'x', 'academic_year': '2569', 'track': 'regular'},
                                     files={'file': ('c.pdf', b'not a pdf', 'application/pdf')})
        self.assertEqual(bad.status_code, 422)
        created = (await self.client.post('/api/v1/school-calendars', data={'name': 'ปฏิทิน 2569', 'academic_year': '2569', 'track': 'regular'},
                                          files={'file': ('ปฏิทิน.pdf', data, 'application/pdf')})).json()
        self.assertEqual((created['state'], created['version'], created['source_hash']), ('draft', 0, sha256(data).hexdigest()))
        self.assertIn('manually', created['parse_note'])
        rid = created['id']
        source = await self.client.get(f'/api/v1/school-calendars/revisions/{rid}/source')
        self.assertEqual((source.status_code, source.content, source.headers['content-type']), (200, data, 'application/pdf'))
        self.assertIn('no-store', source.headers['cache-control'])
        parse = await self.client.post(f'/api/v1/school-calendars/revisions/{rid}/parse', json={'expected_version': 0})
        self.assertEqual((parse.status_code, parse.json()['detail']['code']), (422, 'no_text'))
        invalid = await self.client.put(f'/api/v1/school-calendars/revisions/{rid}', json={'expected_version': 0, 'payload': {'terms': 'x'}})
        self.assertEqual(invalid.status_code, 422)
        empty = await self.client.post(f'/api/v1/school-calendars/revisions/{rid}/publish', json={'expected_version': 0, 'reviewed': True})
        self.assertEqual(empty.status_code, 422)
        payload = calendar_payload(monday(2))
        payload['unresolved'] = ['Week 4 end date unclear']
        saved = (await self.client.put(f'/api/v1/school-calendars/revisions/{rid}', json={'expected_version': 0, 'payload': payload})).json()
        self.assertEqual(saved['version'], 1)
        self.assertEqual(saved['payload']['unresolved'], ['Week 4 end date unclear'])
        self.assertEqual(saved['payload']['terms'][0]['weeks'][0]['page'], 1)
        stale = await self.client.put(f'/api/v1/school-calendars/revisions/{rid}', json={'expected_version': 0, 'payload': payload})
        self.assertEqual(stale.status_code, 409)
        unresolved = await self.client.post(f'/api/v1/school-calendars/revisions/{rid}/publish', json={'expected_version': 1, 'reviewed': True})
        self.assertEqual(unresolved.status_code, 422)
        payload['unresolved'] = []
        await self.client.put(f'/api/v1/school-calendars/revisions/{rid}', json={'expected_version': 1, 'payload': payload})
        self.actor = 3
        self.assertEqual((await self.client.get(f'/api/v1/school-calendars/revisions/{rid}')).status_code, 404)
        self.assertEqual((await self.client.get('/api/v1/school-calendars')).json(), {'can_edit': False, 'can_upload': False, 'calendars': []})
        self.assertEqual((await self.client.post(f'/api/v1/school-calendars/revisions/{rid}/publish', json={'expected_version': 2, 'reviewed': True})).status_code, 403)
        self.actor = 1
        self.assertEqual((await self.client.post(f'/api/v1/school-calendars/revisions/{rid}/publish', json={'expected_version': 2, 'reviewed': False})).status_code, 400)
        published = (await self.client.post(f'/api/v1/school-calendars/revisions/{rid}/publish', json={'expected_version': 2, 'reviewed': True})).json()
        self.assertEqual((published['state'], published['calendar']['published_revision_id']), ('published', rid))
        self.assertEqual((await self.client.put(f'/api/v1/school-calendars/revisions/{rid}', json={'expected_version': 3, 'payload': payload})).status_code, 409)
        with self.assertRaises(Exception):
            async with self.sessions.begin() as db:
                await db.execute(text("UPDATE schoolcalendarrevision SET payload='{}'::jsonb"))
        with self.assertRaises(Exception):
            async with self.sessions.begin() as db:
                await db.execute(text("UPDATE schoolcalendarsource SET filename='changed.pdf'"))
        draft = (await self.client.post(f"/api/v1/school-calendars/{published['calendar_id']}/draft", json={'from_revision_id': rid})).json()
        self.assertEqual((draft['state'], draft['number'], draft['source_hash'], draft['payload']), ('draft', 2, published['source_hash'], published['payload']))
        again = (await self.client.post('/api/v1/school-calendars', data={'name': 'renamed', 'academic_year': '2569', 'track': 'regular'},
                                        files={'file': ('copy.pdf', data, 'application/pdf')})).json()
        self.assertEqual((again['calendar_id'], again['source_id']), (published['calendar_id'], published['source_id']))
        async with self.sessions() as db:
            self.assertEqual(len((await db.exec(select(SchoolCalendarSource))).all()), 1)
        self.actor = 3
        listing = (await self.client.get('/api/v1/school-calendars?year=2569')).json()
        self.assertEqual([(c['published_revision_id'], c['latest_revision_id']) for c in listing['calendars']], [(rid, again['id'])])
        self.assertEqual((await self.client.get(f'/api/v1/school-calendars/revisions/{rid}')).status_code, 200)

    async def text_draft(self, pages=((1, 'ปฏิทินการศึกษา ภาคเรียนที่ 1/2569 สัปดาห์ที่ 1 ...'),), year='2569'):
        """Upload with mocked native text extraction; the PDF bytes are still stored as-is."""
        await self.make_admin(); self.actor = 1
        data = blank_pdf()
        from src.route66_ext.adapters import services_ai_rag_formats as formats
        with patch.object(formats, 'pdf_pages', lambda *a, **k: list(pages)):
            created = await self.client.post('/api/v1/school-calendars', data={'name': 'ปฏิทิน', 'academic_year': year, 'track': 'ภาคปกติ'},
                                             files={'file': ('calendar.pdf', data, 'application/pdf')})
        self.assertEqual(created.status_code, 200, created.text)
        return created.json(), data

    def ai(self, generate):
        from src.route66_ext.adapters import security_features_utils_usage as usage, services_security_rate_limiting as rate
        from src.route66_ext.adapters import security_org_auth as mfa, services_ai_llm as llm
        from unittest.mock import Mock
        self.reserve, self.refund, self.limit, self.mfa = AsyncMock(return_value=1), Mock(), Mock(), AsyncMock()
        self.model, self.generate = AsyncMock(return_value='fixture-model'), generate
        self.ai_patches = [patch.object(target, name, value) for target, name, value in (
            (usage, 'reserve_ai_credit', self.reserve), (usage, 'refund_ai_credit', self.refund),
            (rate, 'enforce_ai_rate_limit', self.limit), (mfa, 'enforce_org_mfa', self.mfa),
            (llm, 'resolve_model_for_org', self.model), (llm, 'generate', generate))]
        for item in self.ai_patches:
            item.start()

    def stop_ai(self):
        for item in reversed(self.ai_patches):
            item.stop()

    async def test_typed_ai_parse_saves_uncertain_draft_for_review_through_native_gate(self):
        draft, data = await self.text_draft()
        self.assertEqual(draft['source_pages'][0]['page'], 1)
        from src.route66_ext.services.calendar_plan import Payload
        start = monday(2)
        parsed = Payload.model_validate({'terms': [{'semester': 1, 'starts_on': start.isoformat(),
            'ends_on': (start + timedelta(days=13)).isoformat(), 'page': 1,
            'weeks': [week(1, start), {**week(2, start + timedelta(days=7), 'midterm'), 'uncertain': True}],
            'closures': [{'affected_on': start.isoformat(), 'makeup_on': None, 'note': 'วันหยุด', 'page': 1}]}],
            'unresolved': ['สัปดาห์สอบกลางภาค: มีการเรียนปกติหรือไม่']})
        self.ai(AsyncMock(return_value=parsed))
        try:
            response = await self.client.post(f"/api/v1/school-calendars/revisions/{draft['id']}/parse", json={'expected_version': 0})
        finally:
            self.stop_ai()
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        self.mfa.assert_awaited_once(); self.limit.assert_called_once_with(1, 1)
        self.assertEqual(self.reserve.await_args.args[0], 1); self.assertEqual(self.reserve.await_args.kwargs, {'amount': 1})
        self.assertEqual(self.model.await_args.kwargs, {'purpose': 'planning'})
        kwargs = self.generate.await_args.kwargs
        self.assertEqual((kwargs['model_name'], kwargs['output_type']), ('fixture-model', Payload))
        self.assertIn('--- Page 1 ---', kwargs['user_prompt'])
        self.refund.assert_not_called()
        self.assertEqual((saved['state'], saved['version'], saved['source_hash']), ('draft', 1, sha256(data).hexdigest()))
        self.assertEqual(saved['payload']['unresolved'], ['สัปดาห์สอบกลางภาค: มีการเรียนปกติหรือไม่'])
        weeks = saved['payload']['terms'][0]['weeks']
        self.assertEqual([(w['rotation'], w['teaching'], w['uncertain']) for w in weeks], [('teaching', True, False), ('midterm', True, True)])
        self.assertTrue(any('Unresolved' in i for i in saved['issues']) and any('uncertain' in i for i in saved['issues']))
        self.assertIn('Check every date', saved['parse_note'])
        refused = await self.client.post(f"/api/v1/school-calendars/revisions/{draft['id']}/publish", json={'expected_version': 1, 'reviewed': True})
        self.assertEqual(refused.status_code, 422)  # a human must resolve the review items first
        reloaded = (await self.client.get(f"/api/v1/school-calendars/revisions/{draft['id']}")).json()
        self.assertEqual((reloaded['state'], reloaded['payload']), ('draft', saved['payload']))

    async def test_known_nrru_calendar_is_read_without_ai_or_credit(self):
        from src.route66_ext.tests.services.test_nrru_calendar_pdf import pages
        draft, _ = await self.text_draft([(p['page'], p['text']) for p in pages()], year='2570')
        self.ai(AsyncMock())
        try:
            response = await self.client.post(f"/api/v1/school-calendars/revisions/{draft['id']}/parse", json={'expected_version': 0})
        finally:
            self.stop_ai()
        self.assertEqual(response.status_code, 200, response.text)
        saved = response.json()
        self.mfa.assert_awaited_once()
        self.limit.assert_not_called(); self.reserve.assert_not_awaited(); self.refund.assert_not_called()
        self.model.assert_not_awaited(); self.generate.assert_not_awaited()
        self.assertEqual((saved['read_method'], saved['version']), ('nrru_calendar_text_v1', 1))
        weeks = {w['number']: w for w in saved['payload']['terms'][0]['weeks']}
        self.assertEqual((weeks[5]['teaching'], weeks[5]['uncertain'], weeks[8]['teaching']), (True, True, False))
        self.assertEqual(len(saved['payload']['unresolved']), 1)
        self.assertIn('NRRU calendar reader (no AI)', saved['parse_note'])
        refused = await self.client.post(f"/api/v1/school-calendars/revisions/{draft['id']}/publish", json={'expected_version': 1, 'reviewed': True})
        self.assertEqual(refused.status_code, 422)  # review questions block publishing until a person resolves them

    async def file_only(self, pages, filename='calendar.pdf'):
        from src.route66_ext.adapters import services_ai_rag_formats as formats
        data = blank_pdf(len(pages))
        with patch.object(formats, 'pdf_pages', lambda *a, **k: list(pages)):
            response = await self.client.post('/api/v1/school-calendars', files={'file': (filename, data, 'application/pdf')})
        return response, data

    async def test_file_only_upload_then_one_action_accept_with_edits(self):
        from src.route66_ext.tests.services.test_nrru_calendar_pdf import pages
        await self.make_admin(); self.actor = 1
        response, data = await self.file_only([(p['page'], p['text']) for p in pages()])
        self.assertEqual(response.status_code, 200, response.text)
        draft = response.json()
        self.assertEqual((draft['calendar']['academic_year'], draft['calendar']['track'], draft['calendar']['name']),
                         (2570, 'ภาคปกติ', 'ปฏิทินการเรียนการสอน ภาคปกติ ปีการศึกษา 2570'))
        no_year = [(1, 'ประกาศมหาวิทยาลัยราชภัฏนครราชสีมา\nปฏิทินการเรียนการสอนสำหรับนักศึกษาภาคปกติ')]
        refused, _ = await self.file_only(no_year)
        self.assertEqual((refused.status_code, refused.json()['detail']['code']), (422, 'invalid_calendar_file'))
        rid = draft['id']
        self.ai(AsyncMock())
        try:
            parsed = (await self.client.post(f'/api/v1/school-calendars/revisions/{rid}/parse', json={'expected_version': 0})).json()
        finally:
            self.stop_ai()
        self.assertEqual((parsed['version'], parsed['read_method']), (1, 'nrru_calendar_text_v1'))
        url = f'/api/v1/school-calendars/revisions/{rid}/publish'
        legacy = await self.client.post(url, json={'expected_version': 1, 'reviewed': True})
        self.assertEqual(legacy.status_code, 422)  # without explicit acceptance, flags still block
        stale = await self.client.post(url, json={'expected_version': 0, 'reviewed': True, 'accept_proposals': True})
        self.assertEqual(stale.status_code, 409)
        broken = {**parsed['payload'], 'terms': [{**parsed['payload']['terms'][0], 'ends_on': '2027-07-01'}]}
        invalid = await self.client.post(url, json={'expected_version': 1, 'reviewed': True, 'accept_proposals': True, 'payload': broken})
        self.assertEqual((invalid.status_code, invalid.json()['detail']['code']), (422, 'not_publishable'))
        edited = parsed['payload']
        edited['terms'][0]['closures'][0]['note'] = 'วันหยุด (แก้ไขแล้ว)'
        done = await self.client.post(url, json={'expected_version': 1, 'reviewed': True, 'accept_proposals': True, 'payload': edited})
        self.assertEqual(done.status_code, 200, done.text)
        published = done.json()
        self.assertEqual((published['id'], published['state'], published['issues'], published['payload']['unresolved']), (rid, 'published', [], []))
        term = published['payload']['terms'][0]
        self.assertEqual(term['closures'][0]['note'], 'วันหยุด (แก้ไขแล้ว)')
        self.assertFalse(any(w['uncertain'] for w in term['weeks']))
        self.assertTrue(published['parse_note'].startswith('Accepted as previewed: '))
        self.assertIn('week 5', published['parse_note']); self.assertIn('NRRU calendar reader', published['parse_note'])
        self.assertLessEqual(len(published['parse_note']), 1000)
        self.assertEqual((await self.client.get(f'/api/v1/school-calendars/revisions/{rid}/source')).content, data)

    async def test_metadata_regroup_copies_source_and_keeps_original_draft(self):
        from src.route66_ext.tests.services.test_nrru_calendar_pdf import pages
        await self.make_admin(); self.actor = 1
        response, data = await self.file_only([(p['page'], p['text']) for p in pages()])
        original = response.json()
        payload = calendar_payload(monday(2))
        moved = await self.client.put(f"/api/v1/school-calendars/revisions/{original['id']}",
                                      json={'expected_version': 0, 'payload': payload, 'metadata': {'academic_year': 2571}})
        self.assertEqual(moved.status_code, 200, moved.text)
        moved = moved.json()
        self.assertNotEqual((moved['id'], moved['calendar_id'], moved['source_id']),
                            (original['id'], original['calendar_id'], original['source_id']))
        self.assertEqual((moved['calendar']['academic_year'], moved['calendar']['track'], moved['source_hash'], moved['version']),
                         (2571, 'ภาคปกติ', original['source_hash'], 1))
        kept = (await self.client.get(f"/api/v1/school-calendars/revisions/{original['id']}")).json()
        self.assertEqual((kept['calendar_id'], kept['source_id'], kept['payload'], kept['state'], kept['version']),
                         (original['calendar_id'], original['source_id'], original['payload'], 'draft', 1))
        self.assertTrue(kept['parse_note'].startswith('Moved to ภาคปกติ 2571 revision 1;'))
        self.assertTrue(kept['parse_note'].endswith(original['parse_note']))  # parser/source notes kept
        self.assertEqual(moved['parse_note'], original['parse_note'])
        for rid in (original['id'], moved['id']):
            self.assertEqual((await self.client.get(f'/api/v1/school-calendars/revisions/{rid}/source')).content, data)
        renamed = (await self.client.put(f"/api/v1/school-calendars/revisions/{moved['id']}",
                   json={'expected_version': 1, 'payload': payload, 'metadata': {'name': 'ปฏิทินใหม่'}})).json()
        self.assertEqual((renamed['id'], renamed['calendar_id'], renamed['calendar']['name']), (moved['id'], moved['calendar_id'], 'ปฏิทินใหม่'))
        done = (await self.client.post(f"/api/v1/school-calendars/revisions/{moved['id']}/publish", json={
            'expected_version': 2, 'reviewed': True, 'metadata': {'track': 'ภาคพิเศษ'}})).json()
        self.assertEqual((done['state'], done['calendar']['track'], done['calendar']['academic_year']), ('published', 'ภาคพิเศษ', 2571))
        self.assertNotEqual(done['id'], moved['id'])
        left = (await self.client.get(f"/api/v1/school-calendars/revisions/{moved['id']}")).json()
        self.assertEqual((left['state'], left['calendar']['published_revision_id']), ('draft', None))
        frozen = await self.client.put(f"/api/v1/school-calendars/revisions/{done['id']}",
                                       json={'expected_version': done['version'], 'payload': payload, 'metadata': {'academic_year': 2572}})
        self.assertEqual(frozen.status_code, 409)  # published grouping never moves
        async with self.sessions() as db:
            sources = (await db.exec(select(SchoolCalendarSource))).all()
        self.assertEqual(len(sources), 3); self.assertEqual({s.sha256 for s in sources}, {sha256(data).hexdigest()})

    async def test_ai_provider_failures_keep_source_and_draft_and_refund_credit(self):
        draft, data = await self.text_draft()
        AINotConfiguredError = type('AINotConfiguredError', (Exception,), {})
        for error, status, code in ((AINotConfiguredError('no provider key'), 403, 'ai_unavailable'),
                                    (RuntimeError('provider timeout'), 502, 'parse_failed')):
            self.ai(AsyncMock(side_effect=error))
            try:
                response = await self.client.post(f"/api/v1/school-calendars/revisions/{draft['id']}/parse", json={'expected_version': 0})
            finally:
                self.stop_ai()
            self.assertEqual((response.status_code, response.json()['detail']['code']), (status, code))
            self.assertIn('manually', response.json()['detail']['message'])
            self.refund.assert_called_once_with(1, 1)
            after = (await self.client.get(f"/api/v1/school-calendars/revisions/{draft['id']}")).json()
            self.assertEqual((after['version'], after['payload'], after['parse_note']), (0, draft['payload'], draft['parse_note']))
            self.assertEqual((await self.client.get(f"/api/v1/school-calendars/revisions/{draft['id']}/source")).content, data)
        # An empty AI reading is a failure: refunded, nothing saved.
        from src.route66_ext.services.calendar_plan import Payload
        self.ai(AsyncMock(return_value=Payload()))
        try:
            response = await self.client.post(f"/api/v1/school-calendars/revisions/{draft['id']}/parse", json={'expected_version': 0})
        finally:
            self.stop_ai()
        self.assertEqual((response.status_code, response.json()['detail']['code']), (502, 'parse_failed'))
        self.refund.assert_called_once_with(1, 1)
        self.assertEqual((await self.client.get(f"/api/v1/school-calendars/revisions/{draft['id']}")).json()['version'], 0)
        # A disabled/over-quota native AI gate is reported precisely, before any model call.
        from fastapi import HTTPException as Denied
        self.ai(AsyncMock())
        self.reserve.side_effect = Denied(403, 'AI is not enabled for this organization')
        try:
            response = await self.client.post(f"/api/v1/school-calendars/revisions/{draft['id']}/parse", json={'expected_version': 0})
        finally:
            self.stop_ai()
        self.assertEqual((response.status_code, response.json()['detail']['code']), (403, 'ai_unavailable'))
        self.assertIn('AI is not enabled', response.json()['detail']['message'])
        self.generate.assert_not_awaited(); self.model.assert_not_awaited()
        manual = await self.client.put(f"/api/v1/school-calendars/revisions/{draft['id']}",
                                       json={'expected_version': 0, 'payload': calendar_payload(monday(2))})
        self.assertEqual(manual.status_code, 200, manual.text)  # manual completion always remains available

    async def test_unmatched_school_class_apply_is_atomic_idempotent_and_grants_nothing(self):
        await self.make_admin()
        revision = await self.published(calendar_payload(monday(1), closures=[
            {'affected_on': monday(2).isoformat(), 'makeup_on': (monday(2) + timedelta(days=5)).isoformat(), 'note': 'วันหยุดราชการ'},
            {'affected_on': (monday(3) + timedelta(days=3)).isoformat(), 'makeup_on': None, 'note': 'ปิดเรียน'}]))
        await self.teacher(3)
        self.actor = 3
        self.timetable[(3, '100', 'P9')] = {'course_code': '990001', 'title': 'วิชาตัวอย่าง', 'meetings': MEETINGS}
        section = self.section()
        async with self.sessions() as db:
            before = ((await db.exec(select(TeachingAssignment))).all(), (await db.exec(select(UserOrganization))).all())
        empty = (await self.client.get('/api/v1/school-calendars/schedules', params=section)).json()
        self.assertEqual((empty['class_id'], empty['sessions']), (None, []))
        preview = await self.preview(revision['id'], section)
        self.assertEqual(preview['changes']['added'], 9)  # 8 regular (two closed) + 1 make-up
        self.assertTrue(any('weekend' in w for w in preview['warnings']))
        async with self.sessions() as db:
            self.assertEqual(len((await db.exec(select(AcademicClass))).all()), 1)  # preview never persists a class
        wrong = await self.client.post('/api/v1/school-calendars/schedules/apply', json={'section': section, 'revision_id': revision['id'],
            'pattern': 'onsite', 'expected_version': 0, 'fingerprint': '0' * 64, 'reviewed': True})
        self.assertEqual(wrong.status_code, 409)
        async with self.sessions() as db:
            self.assertEqual(len((await db.exec(select(AcademicClass))).all()), 1)
            self.assertEqual((await db.exec(select(AttendanceSession))).all(), [])
        saved = await self.apply(revision['id'], section, preview)
        self.assertEqual(saved.status_code, 200, saved.text)
        schedule = saved.json()
        self.assertEqual((schedule['version'], schedule['revision_id'], schedule['pattern']), (1, revision['id'], 'onsite'))
        states = [(s['week_number'], s['state'], s['makeup_for']) for s in schedule['sessions']]
        self.assertIn((2, 'no_class', None), states)
        self.assertIn((2, 'scheduled', monday(2).isoformat()), states)
        self.assertTrue(all(s['attendance_url'].startswith(f"/attendance?class={schedule['class_id']}&session=") for s in schedule['sessions']))
        repeat = await self.apply(revision['id'], section, preview)
        self.assertEqual((repeat.status_code, len(repeat.json()['sessions'])), (200, 9))
        async with self.sessions() as db:
            cls = await db.get(AcademicClass, schedule['class_id'])
            self.assertEqual((cls.course_id, cls.org_id, cls.teacher_user_id, cls.registry_title), (None, 1, 3, 'วิชาตัวอย่าง'))
            after = ((await db.exec(select(TeachingAssignment))).all(), (await db.exec(select(UserOrganization))).all())
            self.assertEqual([a.model_dump() for a in before[0]], [a.model_dump() for a in after[0]])
            self.assertEqual([m.model_dump() for m in before[1]], [m.model_dump() for m in after[1]])
            self.assertIsNone(await access.refresh_course(db, 3, cls.course_id))
            from src.route66_ext.services.academic_projection import project
            evidence = (await db.exec(select(SchoolGoogleEvidence).where(SchoolGoogleEvidence.user_id == 3))).one()
            listed = (await project(db, await db.get(User, 3), 1, evidence))['classes']
            self.assertEqual([(c['id'], c['course_id'], c['course_uuid'], c['course_name']) for c in listed],
                             [(cls.id, None, '', 'วิชาตัวอย่าง')])
        for statement in ("UPDATE attendancesession SET starts_at=starts_at+interval '1 hour'",
                          'UPDATE attendancesession SET academic_week=academic_week+1',
                          'UPDATE attendancesession SET replaces_session_id=id', 'DELETE FROM attendancesession'):
            with self.assertRaises(Exception):
                async with self.sessions.begin() as db:
                    await db.execute(text(statement))
        self.actor = 2  # assigned elsewhere, not this school class's owner
        self.assertEqual((await self.client.get(f"/api/v1/school-calendars/schedules/by-class/{schedule['class_id']}")).status_code, 403)
        self.assertEqual((await self.client.get(f"/api/v1/attendance/classes/{schedule['class_id']}/sessions")).status_code, 403)

    async def test_past_semester_and_exam_dates_are_created_without_attendance_or_guessed_mode(self):
        await self.make_admin()
        data = calendar_payload(monday(-8), count=3)
        for w, number, rotation in zip(data['terms'][0]['weeks'], (7, 8, 9), ('odd', 'midterm', 'even')):
            w.update(number=number, rotation=rotation)
        revision = await self.published(data)
        await self.teacher(3)
        self.actor = 3
        meetings = [{**MEETINGS[1], 'details': 'W:(1-16) เข้าชั้นเรียนในสัปดาห์คู่/เรียนออนไลน์ในสัปดาห์คี่'}]
        self.timetable[(3, '100', 'P9')] = {'course_code': '990001', 'title': 'Synthetic past semester', 'meetings': meetings}
        args = {'section': self.section(), 'revision_id': revision['id'], 'pattern': 'even_onsite'}
        response = await self.client.post('/api/v1/school-calendars/schedules/preview', json=args)
        self.assertEqual(response.status_code, 200, response.text)
        reviewed = response.json()
        self.assertEqual(reviewed['errors'], [])
        self.assertEqual(reviewed['warnings'], [])
        self.assertEqual(reviewed['changes']['added'], 3)
        self.assertEqual([s['mode'] for s in reviewed['sessions']], ['online', None, 'onsite'])
        saved = await self.client.post('/api/v1/school-calendars/schedules/apply', json={**args, 'expected_version': 0,
            'fingerprint': reviewed['fingerprint'], 'reviewed': True})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(len(saved.json()['sessions']), 3)
        async with self.sessions() as db:
            self.assertEqual((await db.exec(select(AttendanceChallenge))).all(), [])
            self.assertEqual((await db.get(SchoolCalendarRevision, revision['id'])).payload, revision['payload'])
        repeated = await self.client.post('/api/v1/school-calendars/schedules/apply', json={**args, 'expected_version': 0,
            'fingerprint': reviewed['fingerprint'], 'reviewed': True})
        self.assertEqual(repeated.json(), saved.json())

    def gapped(self, closures=()):
        """Week 1 is last week (past); weeks 2-4 are upcoming."""
        starts = [monday(-1), monday(1), monday(2), monday(3)]
        return {'timezone': 'Asia/Bangkok', 'terms': [{'semester': 1, 'starts_on': starts[0].isoformat(),
            'ends_on': (starts[-1] + timedelta(days=6)).isoformat(),
            'weeks': [week(i + 1, d) for i, d in enumerate(starts)], 'closures': list(closures)}]}

    async def republish(self, calendar_id, from_id, payload):
        self.actor = 1
        draft = (await self.client.post(f"/api/v1/school-calendars/{calendar_id}/draft", json={'from_revision_id': from_id})).json()
        saved = await self.client.put(f"/api/v1/school-calendars/revisions/{draft['id']}", json={'expected_version': 0, 'payload': payload})
        self.assertEqual(saved.status_code, 200, saved.text)
        done = await self.client.post(f"/api/v1/school-calendars/revisions/{draft['id']}/publish", json={'expected_version': 1, 'reviewed': True})
        self.assertEqual(done.status_code, 200, done.text)
        self.actor = 3
        return done.json()

    async def test_revision_change_protects_past_and_evidence_and_links_future_replacements(self):
        await self.make_admin()
        base = await self.published(self.gapped())
        await self.teacher(3)
        self.actor = 3
        self.timetable[(3, '100', 'P9')] = {'course_code': '990001', 'title': 'วิชาตัวอย่าง', 'meetings': MEETINGS[:1]}
        section = self.section()
        preview = await self.preview(base['id'], section)
        self.assertEqual((preview['changes']['added'], preview['changes']['skipped_past']), (4, 0))
        self.assertEqual([s['action'] for s in preview['sessions']], ['added'] * 4)
        schedule = (await self.apply(base['id'], section, preview)).json()
        by_week = {s['week_number']: s for s in schedule['sessions']}
        self.assertEqual(sorted(by_week), [1, 2, 3, 4])
        self.assertEqual(len((await self.apply(base['id'], section, preview)).json()['sessions']), 4)
        async with self.sessions.begin() as db:
            # Synthetic evidence on week 2; week 1 was backfilled without attendance.
            now = datetime.now(timezone.utc)
            db.add(AttendanceChallenge(session_id=by_week[2]['id'], token_hash='e' * 64, session_version=0, kind='entry',
                created_at=now, expires_at=now + timedelta(minutes=1), created_by=3))
        newer = await self.republish(base['calendar_id'], base['id'], self.gapped([
            {'affected_on': monday(-1).isoformat(), 'makeup_on': None, 'note': 'past closure'},
            {'affected_on': monday(1).isoformat(), 'makeup_on': None, 'note': 'evidence week'},
            {'affected_on': monday(2).isoformat(), 'makeup_on': (monday(2) + timedelta(days=2)).isoformat(), 'note': 'moved'}]))
        current = (await self.client.get(f"/api/v1/school-calendars/schedules/by-class/{schedule['class_id']}")).json()
        self.assertEqual((current['revision_id'], current['newer_revision_id']), (base['id'], newer['id']))
        review = await self.preview(newer['id'], section)
        self.assertEqual(review['protected_count'], 2)
        self.assertEqual((review['changes']['added'], review['changes']['replaced']), (1, 1))
        kept = [s for s in review['sessions'] if s['action'] == 'protected']
        self.assertEqual(sorted((s['week_number'], s['state']) for s in kept), [(1, 'scheduled'), (2, 'scheduled')])
        stale = await self.client.post('/api/v1/school-calendars/schedules/apply', json={'section': section, 'revision_id': newer['id'],
            'pattern': 'onsite', 'expected_version': 0, 'fingerprint': review['fingerprint'], 'reviewed': True})
        self.assertEqual(stale.status_code, 409)
        updated = (await self.apply(newer['id'], section, review)).json()
        self.assertEqual(updated['version'], 2)
        async with self.sessions() as db:
            rows = {r.id: r for r in (await db.exec(select(AttendanceSession))).all()}
        self.assertEqual(rows[by_week[2]['id']].state, 'scheduled')  # evidence-bearing: unchanged
        self.assertEqual(rows[by_week[1]['id']].state, 'scheduled')  # backfilled past: unchanged
        self.assertEqual(rows[by_week[1]['id']].starts_at, datetime.fromisoformat(by_week[1]['starts_at']))
        self.assertEqual((rows[by_week[3]['id']].state, rows[by_week[3]['id']].version), ('no_class', 1))
        makeup = [r for r in rows.values() if r.calendar_kind == 'makeup']
        self.assertEqual([(m.academic_week, m.nominal_on, m.starts_at.astimezone(timezone(timedelta(hours=7))).date()) for m in makeup],
                         [(3, monday(2), monday(2) + timedelta(days=2))])
        # Move the make-up again: the old make-up is kept as superseded history, linked to its replacement.
        third = await self.republish(base['calendar_id'], newer['id'], self.gapped([
            {'affected_on': monday(2).isoformat(), 'makeup_on': (monday(2) + timedelta(days=3)).isoformat(), 'note': 'moved'}]))
        review = await self.preview(third['id'], section)
        final = (await self.apply(third['id'], section, review)).json()
        makeups = [s for s in final['sessions'] if s['calendar_kind'] == 'makeup']
        self.assertEqual([(s['state'], s['superseded']) for s in makeups], [('no_class', True), ('scheduled', False)])
        async with self.sessions() as db:
            latest = await db.get(AttendanceSession, makeups[1]['id'])
            self.assertEqual(latest.replaces_session_id, makeups[0]['id'])

    async def test_preview_warns_about_overlap_with_saved_manual_sessions_without_changing_them(self):
        await self.make_admin()
        revision = await self.published(calendar_payload(monday(1), count=2))
        self.actor = 2
        await self.teacher(2)
        self.timetable[(2, '100', 'P1')] = {'course_code': '990001', 'title': 'วิชาตัวอย่าง', 'meetings': MEETINGS[:1]}
        from zoneinfo import ZoneInfo
        start = datetime.combine(monday(1), datetime.min.time().replace(hour=10), ZoneInfo('Asia/Bangkok'))
        async with self.sessions.begin() as db:
            manual = AttendanceSession(class_id=20, title='Manual lab', starts_at=start, ends_at=start + timedelta(hours=1), created_by=2)
            db.add(manual); await db.flush(); manual_id = manual.id
        preview = await self.preview(revision['id'], self.section('P1'))
        self.assertIn(f'Week 1 meeting overlaps saved session #{manual_id} "Manual lab"', preview['warnings'])
        self.assertFalse(any('Week 2' in w for w in preview['warnings']))
        self.assertEqual(preview['changes']['added'], 2)
        async with self.sessions() as db:
            row = await db.get(AttendanceSession, manual_id)
            self.assertEqual((row.calendar_kind, row.state, row.version, row.replaces_session_id), (None, 'scheduled', 0, None))

    async def test_matched_class_uses_teaching_assignment_and_unmatched_class_attaches_in_place(self):
        await self.make_admin()
        revision = await self.published(calendar_payload(monday(1), count=2))
        self.actor = 2  # assigned native teacher of class 20 (100/P1)
        await self.teacher(2)
        self.timetable[(2, '100', 'P1')] = {'course_code': '990001', 'title': 'วิชาตัวอย่าง', 'meetings': MEETINGS[:1]}
        preview = await self.preview(revision['id'], self.section('P1'))
        saved = (await self.apply(revision['id'], self.section('P1'), preview)).json()
        self.assertEqual(saved['class_id'], 20)
        await self.teacher(3)
        self.actor = 3
        self.timetable[(3, '100', 'P9')] = {'course_code': '990001', 'title': 'วิชาตัวอย่าง', 'meetings': MEETINGS[:1]}
        preview = await self.preview(revision['id'], self.section())
        school = (await self.apply(revision['id'], self.section(), preview)).json()
        session_ids = [s['id'] for s in school['sessions']]
        # Another assigned teacher cannot attach someone else's school class.
        async with self.sessions.begin() as db:
            db.add(TeachingAssignment(course_id=10, user_id=3))
        from contextlib import ExitStack
        async with self.sessions() as db:
            with ExitStack() as stack:
                for p in await self.endpoint_context(db, 2):
                    stack.enter_context(p)
                stack.enter_context(patch.object(connections, 'resources', self._resources))
                self.actor = 2
                self.timetable[(2, '100', 'P9')] = self.timetable[(3, '100', 'P9')]
                with self.assertRaises(HTTPException) as denied:
                    await connections.setup_section(connections.Setup(**self.section(), course_id=10), None, SimpleNamespace(headers={}), db)
                self.assertEqual(denied.exception.status_code, 409)
        async with self.sessions() as db:
            self.actor = 3
            result = await connections.setup_section(connections.Setup(**self.section(), course_id=10), None, SimpleNamespace(headers={}), db)
        self.assertEqual((result['class_id'], result['matched_school_class']), (school['class_id'], True))
        async with self.sessions() as db:
            cls = await db.get(AcademicClass, school['class_id'])
            self.assertEqual(cls.course_id, 10)
            self.assertEqual(sorted((await db.exec(select(AttendanceSession.id).where(AttendanceSession.class_id == cls.id))).all()), sorted(session_ids))
        with self.assertRaises(Exception):
            async with self.sessions.begin() as db:
                await db.execute(text(f"UPDATE academicclass SET course_id=11 WHERE id={school['class_id']}"))
        with self.assertRaises(Exception):
            async with self.sessions.begin() as db:
                await db.execute(text("UPDATE academicclass SET org_id=2 WHERE id=20"))

    @asynccontextmanager
    async def _resources(self, *args):
        yield None, None

    async def test_student_reads_unmatched_schedule_and_checks_in_by_roster(self):
        await self.make_admin()
        revision = await self.published(calendar_payload(monday(1), count=2))
        await self.teacher(3)
        self.actor = 3
        self.timetable[(3, '100', 'P9')] = {'course_code': '990001', 'title': 'วิชาตัวอย่าง', 'meetings': MEETINGS[:1]}
        preview = await self.preview(revision['id'], self.section())
        schedule = (await self.apply(revision['id'], self.section(), preview)).json()
        await self.claim()
        async with self.sessions.begin() as db:
            await roster.serialize(db)
            await roster.apply_roster(db, await db.get(AcademicClass, schedule['class_id']), self.rows('6900000001'), 'c' * 64, 3)
        self.actor = 1
        async with self.sessions.begin() as db:
            row = await db.get(User, 1); row.is_superadmin = False; db.add(row)
        own = await self.client.get(f"/api/v1/school-calendars/schedules/by-class/{schedule['class_id']}")
        self.assertEqual((own.status_code, own.json()['manageable'], len(own.json()['sessions'])), (200, False, 2))
        listed = await self.client.get(f"/api/v1/attendance/classes/{schedule['class_id']}/sessions")
        self.assertEqual((listed.status_code, listed.json()['course_name']), (200, 'วิชาตัวอย่าง'))
        async with self.sessions() as db:
            self.assertEqual(len((await db.exec(select(AcademicRosterEntry))).all()), 1)
        # Same roster student, another organization context: class is not found, nothing leaks.
        self.config = SimpleNamespace(**{**vars(self.config), 'org_id': 2})
        for url in (f"/api/v1/school-calendars/schedules/by-class/{schedule['class_id']}",
                    f"/api/v1/attendance/classes/{schedule['class_id']}/sessions"):
            self.assertEqual((await self.client.get(url)).status_code, 404)

    async def test_migration_backfills_existing_classes_and_named_runner_refuses_versioned_schema(self):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        import importlib.util, os
        import sqlalchemy as sa
        from src.route66_ext.migrations.versions import b3e9c4d1a702_school_calendar as migration
        await self.legacy_schema()

        def upgrade(sync):
            with Operations.context(MigrationContext.configure(sync)):
                migration.upgrade()
            for table in (AcademicClass.__table__, AttendanceSession.__table__, *CALENDAR_TABLES):
                self.assertEqual({c['name'] for c in sa.inspect(sync).get_columns(table.name)}, set(table.columns.keys()))
            with Operations.context(MigrationContext.configure(sync)):
                with self.assertRaises(RuntimeError):
                    migration.downgrade()
        async with self.engine.begin() as conn:
            await conn.run_sync(upgrade)
            self.assertEqual((await conn.execute(text('SELECT id, org_id, course_id FROM academicclass'))).all(), [(20, 1, 10)])
            # Repeat run below is a no-op over the already-migrated schema.
        async with self.engine.begin() as conn:
            def again(sync):
                with Operations.context(MigrationContext.configure(sync)):
                    migration.upgrade()
            await conn.run_sync(again)
        with self.assertRaises(Exception):
            async with self.sessions.begin() as db:
                await db.execute(text("UPDATE attendancesession SET slot_key='x'"))
        await self.legacy_schema()
        spec = importlib.util.spec_from_file_location('named_calendar_migration', Path('/deployment/apply_school_calendar_migration.py'))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        url = 'postgresql://fixture@/fixture?host=/scratch&options=-csearch_path%3D' + self.schema
        with patch.dict(os.environ, {'LEARNHOUSE_SQL_CONNECTION_STRING': url}):
            await asyncio.to_thread(module.main)
            async with self.engine.begin() as conn:
                self.assertEqual((await conn.execute(text('SELECT org_id FROM academicclass'))).scalars().all(), [1])
                await conn.execute(text('CREATE TABLE alembic_version (version_num varchar(32))'))
            with self.assertRaisesRegex(RuntimeError, 'Versioned database'):
                await asyncio.to_thread(module.main)

    async def legacy_schema(self):
        """Pre-calendar deployed shape, with one existing class and session."""
        async with self.engine.begin() as conn:
            for table in reversed(CALENDAR_TABLES):
                await conn.run_sync(lambda sync, t=table: t.drop(sync, checkfirst=True))
            await conn.execute(text('DROP TRIGGER IF EXISTS lh_academic_class_org ON academicclass'))
            for column in ('org_id', 'teacher_user_id', 'registry_title'):
                await conn.execute(text(f'ALTER TABLE academicclass DROP COLUMN IF EXISTS {column}'))
            await conn.execute(text('ALTER TABLE academicclass ALTER COLUMN course_id SET NOT NULL'))
            for column in ('calendar_kind', 'academic_week', 'slot_key', 'nominal_on', 'replaces_session_id', 'rotation', 'mode', 'location', 'note'):
                await conn.execute(text(f'ALTER TABLE attendancesession DROP COLUMN IF EXISTS {column}'))
            await conn.execute(text("""CREATE OR REPLACE FUNCTION lh_attendance_schedule_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Attendance sessions must be retained'; END IF;
 IF ROW(NEW.class_id,NEW.title,NEW.starts_at,NEW.ends_at,NEW.timezone,NEW.grace_minutes,NEW.late_threshold_minutes,NEW.created_by)
 IS DISTINCT FROM ROW(OLD.class_id,OLD.title,OLD.starts_at,OLD.ends_at,OLD.timezone,OLD.grace_minutes,OLD.late_threshold_minutes,OLD.created_by)
 THEN RAISE EXCEPTION 'Attendance schedule cannot be rewritten'; END IF;
 RETURN NEW;
END; $$"""))
            if not (await conn.execute(text('SELECT 1 FROM attendancesession LIMIT 1'))).first():
                now = datetime.now(timezone.utc)
                await conn.execute(text("INSERT INTO attendancesession (class_id,title,starts_at,ends_at,timezone,grace_minutes,late_threshold_minutes,state,version,created_by) VALUES (20,'legacy',:s,:e,'Asia/Bangkok',10,20,'scheduled',0,2)"),
                                   {'s': now, 'e': now + timedelta(hours=1)})

    def linked(self, body, peer='93.184.216.34'):
        """Serve one https link through the real fetch helper and native SSRF guard, without network."""
        import socket
        from src.route66_ext.services import calendar_url
        self.fetched = []

        def handler(request):
            self.fetched.append(str(request.url))
            return httpx.Response(200, content=body, extensions={'network_stream': SimpleNamespace(
                get_extra_info=lambda name: (peer, 443) if name == 'server_addr' else None)})

        resolve = lambda host, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (peer, 0))]
        return [patch('src.services.utils.ssrf_guard.socket.getaddrinfo', resolve),
                patch.object(calendar_url, '_transport', httpx.MockTransport(handler))]

    async def post_link(self, url, body, pages=None, **form):
        from src.route66_ext.adapters import services_ai_rag_formats as formats
        patches = self.linked(body) + ([patch.object(formats, 'pdf_pages', lambda *a, **k: list(pages))] if pages else [])
        for item in patches:
            item.start()
        try:
            return await self.client.post('/api/v1/school-calendars', data={'url': url, **form})
        finally:
            for item in reversed(patches):
                item.stop()

    async def upload_both(self, data, pages, url):
        """The same bytes as a file and as a link; returns both drafts (the source row is shared)."""
        from src.route66_ext.adapters import services_ai_rag_formats as formats
        with patch.object(formats, 'pdf_pages', lambda *a, **k: list(pages)):
            by_file = await self.client.post('/api/v1/school-calendars', files={'file': (url.rsplit('/', 1)[-1], data, 'application/pdf')})
        by_link = await self.post_link(url, data, pages)
        self.assertEqual((by_file.status_code, by_link.status_code), (200, 200), by_file.text + by_link.text)
        return by_file.json(), by_link.json()

    async def read_both(self, drafts):
        self.ai(AsyncMock())
        try:
            read = [await self.client.post(f"/api/v1/school-calendars/revisions/{d['id']}/parse", json={'expected_version': 0}) for d in drafts]
        finally:
            self.stop_ai()
        self.assertEqual([r.status_code for r in read], [200, 200], [r.text for r in read])
        self.reserve.assert_not_awaited(); self.generate.assert_not_awaited(); self.model.assert_not_awaited()
        read = [r.json() for r in read]
        self.assertEqual(read[0]['payload'], read[1]['payload'])  # same bytes by file or link: same dates
        self.assertEqual({r['read_method'] for r in read}, {'nrru_abridged_table_v1'})
        return read

    async def date_calendar_boundaries(self, draft, accept):
        """Stale versions refused, publication as dates only, and no class schedule or session change."""
        publish = f"/api/v1/school-calendars/revisions/{draft['id']}/publish"
        stale = await self.client.post(publish, json={'expected_version': 0, 'reviewed': True, 'accept_proposals': accept})
        self.assertEqual(stale.status_code, 409)
        done = await self.client.post(publish, json={'expected_version': 1, 'reviewed': True, 'accept_proposals': accept})
        self.assertEqual(done.status_code, 200, done.text)
        published = done.json()
        self.assertEqual((published['state'], published['issues'], published['payload']['terms']), ('published', [], []))
        self.assertFalse(any(e['uncertain'] for e in published['payload']['events']))
        again = await self.client.post(f"/api/v1/school-calendars/revisions/{draft['id']}/parse", json={'expected_version': 1})
        self.assertEqual(again.status_code, 409)  # a published calendar never changes
        await self.teacher(3); self.actor = 3
        self.timetable[(3, '100', 'P9')] = {'course_code': '990001', 'title': 'วิชาตัวอย่าง', 'meetings': MEETINGS}
        listing = (await self.client.get('/api/v1/school-calendars')).json()['calendars']
        self.assertEqual([(c['published_revision_id'], c['has_teaching_weeks']) for c in listing if c['id'] == draft['calendar_id']],
                         [(published['id'], False)])  # selectable as dates; course-specific weeks require teacher review
        self.assertEqual((await self.client.get(f"/api/v1/school-calendars/revisions/{draft['id']}")).json()['payload'], published['payload'])
        async def rows():
            async with self.sessions() as db:
                return [len((await db.exec(select(model))).all()) for model in (AcademicClass, ClassSchedule, AttendanceSession)]
        before = await rows()
        section = self.section()
        for step in ('preview', 'apply'):
            body = {'section': section, 'revision_id': published['id'], 'pattern': 'onsite'}
            if step == 'apply':
                body.update(expected_version=0, fingerprint='0' * 64, reviewed=True)
            planned = await self.client.post(f'/api/v1/school-calendars/schedules/{step}', json=body)
            self.assertEqual((planned.status_code, planned.json()['detail']['code']), (422, 'course_dates_required'), step)
        self.assertEqual(await rows(), before)  # no class, schedule or session created or changed
        self.actor = 1
        return published

    async def test_url_upload_gates_and_abridged_table_dates_publish_without_weeks(self):
        from src.route66_ext.tests.services.test_nrru_calendar_pdf import ABRIDGED_TABLE, EDGES, abridged_pages
        from src.route66_ext.tests.services.test_pdf_cells import thai_table_pdf
        from src.route66_ext.adapters import security_org_auth as mfa
        url = 'https://files.example/cal/MIX%202-71.pdf'
        data, pages = thai_table_pdf([(EDGES, ABRIDGED_TABLE)]), [(p['page'], p['text']) for p in abridged_pages()]
        order = []
        guard = AsyncMock(side_effect=lambda *a: order.append('mfa'))
        with patch.object(mfa, 'enforce_org_mfa', guard):
            self.actor = 3  # not a platform administrator: refused before any network
            refused = await self.post_link(url, data, pages)
            self.assertEqual((refused.status_code, self.fetched), (403, []))
            await self.make_admin(); self.actor = 1
            stranger = await self.client.post('/api/v1/school-calendars', data={'url': url}, headers={'Origin': 'https://elsewhere.example'})
            self.assertEqual(stranger.status_code, 403)
            both = await self.client.post('/api/v1/school-calendars', data={'url': url}, files={'file': ('a.pdf', data, 'application/pdf')})
            neither = await self.client.post('/api/v1/school-calendars', data={'name': 'x'})
            self.assertEqual([(r.status_code, r.json()['detail']['code']) for r in (both, neither)], [(422, 'file_or_url')] * 2)
            for bad, code in (('http://files.example/a.pdf', 'invalid_pdf_url'), ('https://[', 'invalid_pdf_url'), (url, 'url_not_pdf')):
                failed = await self.post_link(bad, b'<html>sign in</html>', pages)
                self.assertEqual((failed.status_code, failed.json()['detail']['code']), (422, code))
            self.assertEqual(order, ['mfa'] * 3)  # MFA ran before each authorized fetch attempt
            async with self.sessions() as db:
                self.assertEqual((await db.exec(select(SchoolCalendarSource))).all(), [])
            drafts = await self.upload_both(data, pages, url)
        self.assertEqual({(d['calendar_id'], d['source_id'], d['source_hash']) for d in drafts}, {(drafts[0]['calendar_id'], drafts[0]['source_id'], sha256(data).hexdigest())})
        self.assertEqual((drafts[1]['source_kind'], drafts[1]['calendar']['academic_year'], drafts[1]['calendar']['track']),
                         ('abridged_multi_program', 2571, 'ฉบับรวมหลายรูปแบบ'))
        self.assertEqual((await self.client.get(f"/api/v1/school-calendars/revisions/{drafts[1]['id']}/source")).content, data)
        read = await self.read_both(drafts)
        events = read[0]['payload']['events']
        self.assertEqual((len(events), len(read[0]['payload']['unresolved']), read[0]['version']), (11, 1, 1))
        self.assertEqual({e['kind'] for e in events}, {'opening', 'other', 'final', 'grades', 'midterm'})
        self.assertIn('Imported 11 academic dates', read[0]['parse_note']); self.assertIn('no class sessions are generated', read[0]['parse_note'])
        legacy = await self.client.post(f"/api/v1/school-calendars/revisions/{drafts[0]['id']}/publish", json={'expected_version': 1, 'reviewed': True})
        self.assertEqual(legacy.status_code, 422)  # the unreadable "31 ก.พ." question blocks until accepted
        await self.date_calendar_boundaries(drafts[0], accept=True)

    async def private_calendar(self, user=3):
        self.actor = user
        response = await self.client.post('/api/v1/school-calendars',
            data={'name': 'Private teacher calendar', 'academic_year': '2569', 'track': 'ภาคปกติ'},
            files={'file': ('private.pdf', blank_pdf(), 'application/pdf')})
        self.assertEqual(response.status_code, 200, response.text)
        draft = response.json()
        response = await self.client.post(f"/api/v1/school-calendars/revisions/{draft['id']}/publish",
            json={'expected_version': 0, 'reviewed': True, 'payload': calendar_payload(monday(2))})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def test_private_calendars_isolate_sources_drafts_and_shared_groups(self):
        await self.make_admin(); shared = await self.published(calendar_payload(monday(2)))
        await self.teacher(3); private = await self.private_calendar()
        again = await self.private_calendar()
        await self.teacher(2); other = await self.private_calendar(2)
        self.assertNotEqual(other['calendar_id'], private['calendar_id'])
        self.assertEqual(private['calendar']['scope'], 'teacher')
        self.assertTrue(private['calendar']['can_edit'])
        self.assertEqual(len({r['calendar_id'] for r in (shared, private, again)}), 3)
        self.assertTrue((await self.client.get('/api/v1/school-calendars')).json()['can_upload'])
        for actor in (1, 2):
            self.actor = actor
            listing = (await self.client.get('/api/v1/school-calendars')).json()['calendars']
            self.assertEqual(private['calendar_id'] in {c['id'] for c in listing}, actor == 1)
            for suffix in ('', '/source'):
                self.assertEqual((await self.client.get(f"/api/v1/school-calendars/revisions/{private['id']}{suffix}")).status_code,
                                 200 if actor == 1 else 404)
        self.actor = 3
        self.assertEqual((await self.client.post('/api/v1/school-calendars', data={'scope': 'organization'},
            files={'file': ('a.pdf', blank_pdf())})).status_code, 403)
        self.assertEqual((await self.client.post(f"/api/v1/school-calendars/{shared['calendar_id']}/draft",
            json={'from_revision_id': shared['id']})).status_code, 403)
        draft = (await self.client.post(f"/api/v1/school-calendars/{private['calendar_id']}/draft",
            json={'from_revision_id': private['id']})).json()
        self.assertEqual(draft['derived_from_revision_id'], private['id'])
        moved = await self.client.put(f"/api/v1/school-calendars/revisions/{draft['id']}", json={
            'expected_version': 0, 'payload': draft['payload'], 'metadata': {'track': 'Private regroup'}})
        self.assertEqual(moved.status_code, 200, moved.text)
        self.assertEqual(moved.json()['calendar']['scope'], 'teacher')
        self.config = SimpleNamespace(**{**vars(self.config), 'org_id': 2})
        self.assertEqual((await self.client.get(f"/api/v1/school-calendars/revisions/{private['id']}/source")).status_code, 404)
        with self.assertRaises(Exception):
            async with self.sessions.begin() as db:
                await db.execute(text("UPDATE schoolcalendar SET scope='organization', owner_user_id=NULL WHERE id=:id"), {'id': private['calendar_id']})

    async def test_private_proposal_attachment_is_frozen_authorized_and_idempotent(self):
        await self.teacher(3); private = await self.private_calendar()
        self.timetable[(3, '100', 'P9')] = {'course_code': '990001', 'title': 'Synthetic proposal', 'meetings': MEETINGS}
        response = await self.client.post('/api/v1/academic-classes/connections/requests', json=self.section())
        self.assertEqual(response.status_code, 200, response.text)
        request_id = response.json()['id']
        path = f'/api/v1/academic-classes/connections/requests/{request_id}/calendar'
        draft = (await self.client.post(f"/api/v1/school-calendars/{private['calendar_id']}/draft",
            json={'from_revision_id': private['id']})).json()
        self.assertEqual((await self.client.post(path, json={'revision_id': draft['id']})).status_code, 409)
        for _ in range(2):
            attached = await self.client.post(path, json={'revision_id': private['id']})
            self.assertEqual(attached.status_code, 200, attached.text)
            self.assertEqual([a['revision_id'] for a in attached.json()['calendar_attachments']], [private['id']])
        self.actor = 2
        self.assertEqual((await self.client.post(path, json={'revision_id': private['id']})).status_code, 404)
        self.assertEqual((await self.client.get('/api/v1/academic-classes/connections/requests')).json()['requests'], [])
        await self.make_admin(); self.actor = 1
        inbox = (await self.client.get('/api/v1/academic-classes/connections/requests')).json()['requests']
        self.assertEqual(inbox[0]['calendar_attachments'][0]['revision_id'], private['id'])
        self.assertEqual((await self.client.get(f"/api/v1/school-calendars/revisions/{private['id']}/source")).content, blank_pdf())
        async with self.sessions() as db:
            self.assertEqual(len((await db.exec(select(SchoolCalendarAttachment))).all()), 1)
            self.assertEqual((await db.exec(select(ClassSchedule))).all(), [])
            self.assertEqual((await db.exec(select(AttendanceSession))).all(), [])
        for sql in ('DELETE FROM schoolcalendarattachment', 'TRUNCATE schoolcalendarattachment',
                    "UPDATE schoolcalendarattachment SET calendar_revision_id=" + str(draft['id'])):
            with self.assertRaises(Exception):
                async with self.sessions.begin() as db:
                    await db.execute(text(sql))

    async def test_private_url_provenance_and_admin_copy_do_not_change_class_pins(self):
        from src.route66_ext.adapters import security_org_auth as mfa
        await self.make_admin(); shared = await self.published(calendar_payload(monday(2)))
        await self.teacher(3); self.actor = 3
        self.timetable[(3, '100', 'P9')] = {'course_code': '990001', 'title': 'Synthetic section', 'meetings': MEETINGS}
        preview = await self.preview(shared['id'], self.section())
        saved = await self.apply(shared['id'], self.section(), preview)
        self.assertEqual(saved.status_code, 200, saved.text)
        schedule = saved.json()
        with patch.object(mfa, 'enforce_org_mfa', AsyncMock()):
            response = await self.post_link('https://files.example/private.pdf', blank_pdf(),
                name='Private URL', academic_year='2569', track='ภาคปกติ')
        self.assertEqual(response.status_code, 200, response.text)
        draft = response.json(); url = draft['source_url']
        with self.assertRaises(Exception):
            async with self.sessions.begin() as db:
                await db.execute(text("UPDATE schoolcalendarrevision SET source_url='https://changed.example/a.pdf' WHERE id=:id"), {'id': draft['id']})
        self.assertEqual((url, draft['resolved_url']), ('https://files.example/private.pdf',) * 2)
        self.assertIsNotNone(draft['fetched_at'])
        private = (await self.client.post(f"/api/v1/school-calendars/revisions/{draft['id']}/publish", json={
            'expected_version': 0, 'reviewed': True, 'payload': calendar_payload(monday(3))})).json()
        self.assertEqual((await self.client.post(f"/api/v1/school-calendars/revisions/{private['id']}/share",
            json={'reviewed': True})).status_code, 403)
        self.actor = 1
        copied = await self.client.post(f"/api/v1/school-calendars/revisions/{private['id']}/share", json={'reviewed': True})
        self.assertEqual(copied.status_code, 200, copied.text)
        copy = copied.json()
        self.assertEqual((copy['state'], copy['calendar']['scope'], copy['calendar_id']), ('draft', 'organization', shared['calendar_id']))
        self.assertEqual((copy['source_hash'], copy['source_url'], copy['fetched_at'], copy['derived_from_revision_id']),
                         (private['source_hash'], url, private['fetched_at'], private['id']))
        published = await self.client.post(f"/api/v1/school-calendars/revisions/{copy['id']}/publish", json={'expected_version': 0, 'reviewed': True})
        self.assertEqual(published.status_code, 200, published.text)
        async with self.sessions() as db:
            self.assertEqual((await db.get(ClassSchedule, schedule['class_id'])).revision_id, shared['id'])
            self.assertEqual((await db.get(SchoolCalendar, private['calendar_id'])).scope, 'teacher')
            self.assertEqual((await db.get(SchoolCalendarRevision, private['id'])).source_url, url)
        self.actor = 2
        self.assertEqual((await self.client.get(f"/api/v1/school-calendars/revisions/{private['id']}/source")).status_code, 404)
        self.assertEqual((await self.client.get(f"/api/v1/school-calendars/revisions/{copy['id']}/source")).content, blank_pdf())

    async def test_private_calendar_migration_dry_run_preserves_existing_rows(self):
        import importlib.util, os
        import sqlalchemy as sa
        await self.make_admin(); shared = await self.published(calendar_payload(monday(2)))
        async with self.engine.begin() as conn:
            await conn.execute(text('DROP TABLE schoolcalendarattachment'))
            for table, columns in [('schoolcalendar', ('scope', 'owner_user_id')),
                ('schoolcalendarrevision', ('source_url', 'resolved_url', 'fetched_at', 'derived_from_revision_id'))]:
                for column in columns:
                    await conn.execute(text(f'ALTER TABLE {table} DROP COLUMN {column}'))
            await conn.execute(text('ALTER TABLE schoolcalendar ADD CONSTRAINT uq_school_calendar_track UNIQUE (org_id,academic_year,track)'))
        spec = importlib.util.spec_from_file_location('private_calendar_migration', '/deployment/apply_private_calendar_migration.py')
        runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        url = 'postgresql://fixture@/fixture?host=/scratch&options=-csearch_path%3D' + self.schema
        with patch.dict(os.environ, {'LEARNHOUSE_SQL_CONNECTION_STRING': url}):
            await asyncio.to_thread(runner.main)
            await asyncio.to_thread(runner.main)  # repeat is safe
            async with self.sessions() as db:
                row = await db.get(SchoolCalendar, shared['calendar_id'])
                self.assertEqual((row.scope, row.owner_user_id), ('organization', None))
                self.assertEqual((await db.get(SchoolCalendarRevision, shared['id'])).source_url, None)
            async with self.engine.begin() as conn:
                def verify(sync):
                    for table in CALENDAR_TABLES:
                        self.assertEqual({c['name'] for c in sa.inspect(sync).get_columns(table.name)}, set(table.columns.keys()))
                await conn.run_sync(verify)
                await conn.execute(text('CREATE TABLE alembic_version (version_num varchar(32))'))
            with self.assertRaisesRegex(RuntimeError, 'Versioned database'):
                await asyncio.to_thread(runner.main)

    async def test_private_actual_link_source_proof(self):
        """Opt-in: the live-retained MIX bytes and page text (exported read-only), by file and by link."""
        import json, os
        folder = os.getenv('LEARNHOUSE_TEST_PRIVATE_SOURCE')
        if not folder:
            self.skipTest('private source not mounted')
        data = Path(folder, 'live-source-3.pdf').read_bytes()
        pages = [(p['page'], p['text']) for p in json.loads(Path(folder, 'live-source-3-pages.json').read_text())]
        url = Path(folder, 'url.txt').read_text().strip()
        await self.make_admin(); self.actor = 1
        with patch('src.route66_ext.adapters.security_org_auth.enforce_org_mfa', AsyncMock()):
            drafts = await self.upload_both(data, pages, url)
        self.assertEqual(self.fetched, [url])
        stored = (await self.client.get(f"/api/v1/school-calendars/revisions/{drafts[1]['id']}/source")).content
        self.assertEqual((stored, drafts[0]['source_hash']), (data, sha256(data).hexdigest()))
        read = await self.read_both(drafts)
        expected = json.loads(Path(folder, 'actual-events-proof.json').read_text())
        self.assertEqual(read[0]['payload']['events'], expected['payload']['events'])
        self.assertEqual(len(read[0]['payload']['events']), 75)
        published = await self.date_calendar_boundaries(drafts[0], accept=False)
        Path(folder, 'pg-dto-proof.json').write_text(json.dumps({'upload': drafts, 'parse': read, 'published': published},
                                                                ensure_ascii=False, indent=1, default=str))


    async def test_date_calendar_course_schedule_review_apply_and_reload(self):
        await self.make_admin()
        first = monday(2)
        payload = {'events': [{'semester': 1, 'program': program, 'kind': kind, 'title': kind,
            'starts_on': str(first + timedelta(days=offset)), 'ends_on': str(first + timedelta(days=offset))}
            for program, kind, offset in [('A', 'opening', 0), ('A', 'final', 28), ('B', 'opening', 7), ('B', 'final', 42)]]}
        published = await self.published(payload)
        await self.teacher(3); self.actor = 3
        self.timetable[(3, '100', 'P9')] = {'course_code': '990001', 'title': 'วิชาตัวอย่าง', 'meetings': MEETINGS}
        catalog = (await self.client.get('/api/v1/school-calendars')).json()['calendars']
        self.assertEqual([o['program'] for o in catalog[0]['planning_options']], ['A', 'B'])
        planning = {'program': 'A', 'starts_on': str(first), 'ends_on': str(first + timedelta(days=20)),
                    'closures': [{'affected_on': str(first + timedelta(days=3)), 'makeup_on': str(first + timedelta(days=5)), 'note': 'Course holiday'}]}
        planning = api.planner.CoursePlanning.model_validate(planning).model_dump(mode='json')
        body = {'section': self.section(), 'revision_id': published['id'], 'pattern': 'even_onsite', 'hybrid_start': 'online', 'planning': planning}
        response = await self.client.post('/api/v1/school-calendars/schedules/preview', json=body)
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()
        self.assertEqual(preview['errors'], [])
        self.assertEqual(preview['changes']['added'], 7)
        self.assertTrue(any('Review the dated' in w for w in preview['warnings']))
        self.assertEqual({(s['week_number'], s['mode']) for s in preview['sessions']}, {(1, 'online'), (2, 'onsite'), (3, 'online')})
        missing_start = await self.client.post('/api/v1/school-calendars/schedules/preview', json={**body, 'hybrid_start': None})
        self.assertEqual(missing_start.json()['errors'], [])
        self.assertEqual(len(missing_start.json()['sessions']), 7)
        self.assertTrue(all(s['mode'] is None for s in missing_start.json()['sessions']))
        invalid_start = await self.client.post('/api/v1/school-calendars/schedules/preview', json={**body, 'hybrid_start': 'unknown'})
        self.assertEqual(invalid_start.status_code, 422)
        apply = {**body, 'expected_version': preview['version'], 'fingerprint': preview['fingerprint'], 'reviewed': True}
        changed = {**apply, 'planning': {**planning, 'ends_on': str(first + timedelta(days=27))}}
        self.assertEqual((await self.client.post('/api/v1/school-calendars/schedules/apply', json=changed)).status_code, 409)
        saved = await self.client.post('/api/v1/school-calendars/schedules/apply', json=apply)
        self.assertEqual(saved.status_code, 200, saved.text)
        saved = saved.json()
        self.assertEqual(saved['planning'], planning)
        self.assertEqual(saved['hybrid_start'], 'online')
        wrong_mode = await self.client.post('/api/v1/school-calendars/schedules/apply', json={**apply, 'hybrid_start': 'onsite'})
        self.assertEqual(wrong_mode.status_code, 409)
        repeated = await self.client.post('/api/v1/school-calendars/schedules/apply', json=apply)
        self.assertEqual((repeated.status_code, repeated.json()['version']), (200, 1))
        loaded = (await self.client.get('/api/v1/school-calendars/schedules', params=self.section())).json()
        self.assertEqual(loaded['planning'], planning)
        self.assertEqual(loaded['hybrid_start'], 'online')
        self.assertEqual(len(loaded['sessions']), 7)
        self.assertEqual({(s['week_number'], s['mode']) for s in loaded['sessions']}, {(1, 'online'), (2, 'onsite'), (3, 'online')})
        self.assertFalse(loaded['syllabus_available'])  # no inferred native course or authoring rights
        original = (await self.client.get(f"/api/v1/school-calendars/revisions/{published['id']}")).json()
        self.assertEqual(original['payload'], published['payload'])
        self.assertEqual(original['payload']['terms'], [])
        self.assertEqual((await self.client.post(f"/api/v1/school-calendars/schedules/by-class/{saved['class_id']}/syllabus", json={'expected_version': 1})).status_code, 409)
        await self.claim()
        async with self.sessions.begin() as db:
            await roster.serialize(db)
            await roster.apply_roster(db, await db.get(AcademicClass, saved['class_id']), self.rows('6900000001'), 'c' * 64, 3)
            user = await db.get(User, 1); user.is_superadmin = False; db.add(user)
        self.actor = 1
        own = await self.client.get(f"/api/v1/school-calendars/schedules/by-class/{saved['class_id']}")
        self.assertEqual((own.status_code, own.json()['manageable']), (200, False))
        self.assertEqual(own.json()['sessions'], loaded['sessions'])

    async def test_official_rule_matches_pdf_dates_and_syllabus_before_attendance_save(self):
        from src.route66_ext.adapters import native_course_syllabus as native
        from src.route66_ext.adapters.native_learning_access_test_support import CourseChapter, ChapterActivity, ResourceAuthor, UserGroup, UserGroupResource, UserGroupUser, ActivityVersion
        async with self.engine.begin() as conn:
            for table in (native.Chapter.__table__, native.Activity.__table__, CourseChapter.__table__, ChapterActivity.__table__, ResourceAuthor.__table__, UserGroup.__table__, UserGroupResource.__table__, UserGroupUser.__table__, ActivityVersion.__table__):
                await conn.run_sync(table.create)
        await self.make_admin()
        data = calendar_payload(monday(2))
        for index, w in enumerate(data['terms'][0]['weeks']):
            w['rotation'] = 'odd' if index == 0 else 'even'
            w['teaching_dates'] = [w['starts_on']]
        revision = await self.published(data)
        detail = '990001 (P1) 3 (2-2-5) W:(1-16) 27.03.03 (เข้าชั้นเรียนในสัปดาห์คู่/เรียนออนไลน์ในสัปดาห์คี่)'
        meetings = [{**MEETINGS[0], 'details': detail}]
        self.timetable[(2, '100', 'P1')] = {'course_code': '990001', 'title': 'Synthetic course 10', 'meetings': meetings}
        self.actor = 2
        path = '/api/v1/school-calendars/schedules/by-class/20/syllabus'
        body = {'expected_version': 0, 'revision_id': revision['id'], 'section': self.section('P1'), 'language': 'th'}
        self.assertEqual((await self.client.post(path, json={**body, 'section': self.section('P9')})).status_code, 409)
        with patch('src.services.courses.chapters.index_course'), patch('src.services.courses.activities.activities.index_activity'):
            created = await self.client.post(path, json=body)
        self.assertEqual(created.status_code, 200, created.text)
        self.assertTrue(created.json()['created'])
        async with self.sessions() as db:
            activity = (await db.exec(select(native.Activity))).one()
            text = str(activity.content)
            self.assertIn('3 (2-2-5)', text)
            self.assertIn('27.03.03', text)
            self.assertIn('ที่มหาวิทยาลัย', text)
            self.assertIn('ออนไลน์', text)
            self.assertEqual((await db.exec(select(ClassSchedule))).all(), [])
            self.assertEqual((await db.exec(select(AttendanceSession))).all(), [])
            self.assertEqual((await db.exec(select(ResourceAuthor))).all(), [])
        del self.timetable[(2, '100', 'P1')]
        reopened = await self.client.post(path, json=body)
        self.assertEqual((reopened.status_code, reopened.json()['created']), (200, False))
        self.timetable[(2, '100', 'P1')] = {'course_code': '990001', 'title': 'Synthetic course 10', 'meetings': meetings}
        args = {'section': self.section('P1'), 'revision_id': revision['id'], 'pattern': 'even_onsite', 'hybrid_start': 'onsite'}
        reviewed = await self.client.post('/api/v1/school-calendars/schedules/preview', json=args)
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        self.assertEqual(reviewed.json()['errors'], [])
        self.assertEqual([s['mode'] for s in reviewed.json()['sessions']], ['online', 'onsite', 'onsite', 'onsite'])
        saved = await self.client.post('/api/v1/school-calendars/schedules/apply', json={**args,
            'expected_version': 0, 'fingerprint': reviewed.json()['fingerprint'], 'reviewed': True})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertIsNone(saved.json()['hybrid_start'])
        self.assertEqual([s['mode'] for s in saved.json()['sessions']], ['online', 'onsite', 'onsite', 'onsite'])
        self.assertEqual((await self.client.get('/api/v1/school-calendars/schedules/by-class/20')).json(), saved.json())
        self.assertEqual(saved.json()['school_pattern'], 'even_onsite')
        self.assertIsNone(saved.json()['policy_override'])
        exception = {**args, 'pattern': 'online', 'policy_override': 'online'}
        reviewed_override = await self.client.post('/api/v1/school-calendars/schedules/preview', json=exception)
        self.assertEqual(reviewed_override.status_code, 200, reviewed_override.text)
        self.assertEqual({s['mode'] for s in reviewed_override.json()['sessions']}, {'online'})
        applied_override = await self.client.post('/api/v1/school-calendars/schedules/apply', json={**exception,
            'expected_version': 1, 'fingerprint': reviewed_override.json()['fingerprint'], 'reviewed': True})
        self.assertEqual(applied_override.status_code, 200, applied_override.text)
        self.assertEqual((applied_override.json()['school_pattern'], applied_override.json()['policy_override']), ('even_onsite', 'online'))
        self.assertIsNone(applied_override.json()['hybrid_start'])
        self.assertEqual((await self.client.get('/api/v1/school-calendars/schedules/by-class/20')).json(), applied_override.json())
        restored_preview = await self.client.post('/api/v1/school-calendars/schedules/preview', json=args)
        restored = await self.client.post('/api/v1/school-calendars/schedules/apply', json={**args,
            'expected_version': 2, 'fingerprint': restored_preview.json()['fingerprint'], 'reviewed': True})
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertIsNone(restored.json()['policy_override'])
        self.assertEqual([s['mode'] for s in restored.json()['sessions'] if not s['superseded']], ['online', 'onsite', 'onsite', 'onsite'])
        async with self.sessions() as db:
            self.assertEqual((await db.get(SchoolCalendarRevision, revision['id'])).payload, revision['payload'])
            self.assertEqual(str((await db.exec(select(native.Activity))).one().content), text)

    async def test_native_syllabus_draft_is_course_owned_unpublished_and_not_overwritten(self):
        from src.route66_ext.adapters import native_course_syllabus as native
        from src.route66_ext.adapters.native_learning_access_test_support import CourseChapter, ChapterActivity, ResourceAuthor, UserGroup, UserGroupResource, UserGroupUser, PublicUser, read_native_activity, ActivityVersion, ActivityUpdate, update_activity, get_editor_bootstrap, check_resource_access, AccessAction, ResourceAccessChecker, UserOrganization
        from src.route66_ext.tests.services.test_native_google_sessions import request as native_request
        async with self.engine.begin() as conn:
            for table in (native.Chapter.__table__, native.Activity.__table__, CourseChapter.__table__, ChapterActivity.__table__, ResourceAuthor.__table__, UserGroup.__table__, UserGroupResource.__table__, UserGroupUser.__table__, ActivityVersion.__table__):
                await conn.run_sync(table.create)
        await self.make_admin()
        revision = await self.published(calendar_payload(monday(2)))
        from src.route66_ext.adapters.db_courses_courses import Course
        async with self.sessions.begin() as db:
            course = await db.get(Course, 10); course.public = True; course.published = True; db.add(course)
        path = '/api/v1/school-calendars/schedules/by-class/20/syllabus'
        body = {'expected_version': 0, 'revision_id': revision['id']}
        self.actor = 3  # not an assigned teacher or native author
        denied = await self.client.post(path, json=body)
        self.assertEqual(denied.status_code, 403, denied.text)
        self.actor = 2  # approved course teacher, no native author/admin grant
        def activity_request(uuid, suffix=''):
            req = native_request(); req.scope['path'] = '/api/v1/activities/' + uuid + suffix
            return req
        with patch('src.services.courses.chapters.index_course'), patch.object(native, 'create_activity', AsyncMock(side_effect=HTTPException(503, 'Synthetic creation failure'))):
            failed = await self.client.post(path, json=body)
        self.assertEqual(failed.status_code, 503)
        async with self.sessions() as db:
            self.assertEqual((await db.exec(select(native.Chapter))).all(), [])
            self.assertEqual((await db.exec(select(native.Activity))).all(), [])
        with patch('src.services.courses.chapters.index_course'), patch('src.services.courses.activities.activities.index_activity'):
            results = await asyncio.gather(*[self.client.post(path, json={**body, 'language': 'th'}) for _ in range(2)])
        self.assertEqual([r.status_code for r in results], [200, 200], [r.text for r in results])
        self.assertEqual(sorted(r.json()['created'] for r in results), [False, True])
        created = next(r for r in results if r.json()['created'])
        self.assertEqual(created.status_code, 200, created.text)
        self.assertTrue(created.json()['created'])
        self.assertEqual(created.json()['editor_url'], f"/course/fixture_10/activity/{created.json()['activity_uuid'].removeprefix('activity_')}/edit")
        async with self.sessions.begin() as db:
            activity = (await db.exec(select(native.Activity))).one()
            self.assertFalse(activity.published)
            self.assertEqual(activity.course_id, 10)
            self.assertIn('2569', str(activity.content))
            self.assertIn('Synthetic course 10', str(activity.content))
            self.assertEqual(activity.extra_metadata['route66_syllabus']['calendar_revision_id'], revision['id'])
        async with self.sessions() as db:
            learner = PublicUser.model_validate(await db.get(User, 3))
            with self.assertRaises(HTTPException) as denied:
                await read_native_activity(native_request(), created.json()['activity_uuid'], learner, db)
            self.assertEqual(denied.exception.status_code, 404)
        authored = {'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Teacher-authored syllabus'}]}]}
        async with self.sessions() as db:
            teacher = PublicUser.model_validate(await db.get(User, 2))
            self.assertFalse(teacher.is_superadmin)
            bootstrap = await get_editor_bootstrap(activity_request(created.json()['activity_uuid'], '/editor-bootstrap'), created.json()['activity_uuid'], teacher, db)
            self.assertEqual(bootstrap.activity.content, activity.content)
            with patch('src.services.courses.activities.activities.index_activity'), patch('src.services.courses.activities.versioning.dispatch_webhooks', AsyncMock()):
                updated = await update_activity(activity_request(created.json()['activity_uuid']), ActivityUpdate(content=authored, published=True), created.json()['activity_uuid'], teacher, db)
            self.assertEqual(updated.content, authored)
            self.assertTrue(updated.published)
            previous = (await db.exec(select(ActivityVersion))).one()
            self.assertEqual((previous.created_by_id, previous.version_number), (2, 1))
            self.assertEqual(previous.content, bootstrap.activity.content)
            self.assertEqual(updated.current_version, 2)
            self.assertEqual((await db.exec(select(ResourceAuthor))).all(), [])
        repeated = await self.client.post(path, json=body)
        self.assertEqual((repeated.status_code, repeated.json()['created']), (200, False))
        self.assertEqual(created.json()['activity_uuid'], repeated.json()['activity_uuid'])
        async with self.sessions() as db:
            activity = (await db.exec(select(native.Activity))).one()
            self.assertEqual(activity.content, authored)
            self.assertTrue(activity.published)
            learner = PublicUser.model_validate(await db.get(User, 3))
            self.assertEqual((await read_native_activity(native_request(), activity.activity_uuid, learner, db)).content, authored)
            self.assertEqual((await db.exec(select(AttendanceSession))).all(), [])
            self.assertEqual((await db.exec(select(ClassSchedule))).all(), [])
        self.assertEqual((await self.client.post(path, json={**body, 'expected_version': 1})).status_code, 409)
        # A different program's published syllabus must not be selected or rewritten.
        async with self.sessions.begin() as db:
            activity = (await db.exec(select(native.Activity))).one()
            activity.extra_metadata = {**activity.extra_metadata, 'route66_syllabus': {
                **activity.extra_metadata['route66_syllabus'], 'program': 'Another synthetic program'}}
            db.add(activity)
        with patch('src.services.courses.chapters.index_course'), patch('src.services.courses.activities.activities.index_activity'):
            different = await self.client.post(path, json=body)
        self.assertEqual((different.status_code, different.json()['created']), (200, True))
        self.assertNotEqual(created.json()['activity_uuid'], different.json()['activity_uuid'])
        async with self.sessions() as db:
            activities = (await db.exec(select(native.Activity))).all()
            self.assertEqual(len(activities), 2)
            original = next(a for a in activities if a.activity_uuid == created.json()['activity_uuid'])
            self.assertEqual(original.content, authored); self.assertTrue(original.published)
            new = next(a for a in activities if a.activity_uuid == different.json()['activity_uuid'])
            self.assertIn(new.extra_metadata['route66_syllabus']['program'], new.name)
            self.assertFalse(new.published)
            self.timetable[(2, '100', 'P1')] = {'course_code': '990001', 'title': 'Synthetic course 10', 'meetings': MEETINGS}
            hybrid = {'section': self.section('P1'), 'revision_id': revision['id'], 'pattern': 'even_onsite', 'hybrid_start': 'onsite'}
            reviewed = await self.client.post('/api/v1/school-calendars/schedules/preview', json=hybrid)
            self.assertEqual(reviewed.status_code, 200, reviewed.text)
            self.assertEqual(reviewed.json()['errors'], [])
            applied = await self.client.post('/api/v1/school-calendars/schedules/apply', json={**hybrid,
                'expected_version': reviewed.json()['version'], 'fingerprint': reviewed.json()['fingerprint'], 'reviewed': True})
            self.assertEqual(applied.status_code, 200, applied.text)
            self.assertEqual((applied.json()['class_id'], applied.json()['manageable'], applied.json()['hybrid_start']), (20, True, 'onsite'))
            self.assertEqual({(s['week_number'], s['mode']) for s in applied.json()['sessions']},
                             {(1, 'onsite'), (2, 'online'), (3, 'onsite'), (4, 'online')})
            self.assertEqual(original.content, authored)
            teacher = PublicUser.model_validate(await db.get(User, 2))
            req = activity_request(new.activity_uuid)
            # Ordinary course authoring remains denied, as do other-course and delete access.
            ordinary = native_request(); ordinary.scope['path'] = '/api/v1/courses/course_fixture_10'
            for request, uuid, action in [(ordinary, 'course_fixture_10', AccessAction.UPDATE),
                (req, 'course_fixture_11', AccessAction.UPDATE), (req, 'course_fixture_10', AccessAction.DELETE),
                (req, 'course_fixture_10', AccessAction.CREATE)]:
                self.assertFalse((await check_resource_access(request, db, teacher, uuid, action, raise_on_deny=False)).allowed)
            with patch.object(ResourceAccessChecker, '_enforce_org_mfa_policy', AsyncMock(side_effect=HTTPException(403, 'MFA required'))):
                with self.assertRaises(HTTPException) as mfa:
                    await check_resource_access(activity_request(new.activity_uuid), db, teacher, 'course_fixture_10', AccessAction.UPDATE)
                self.assertEqual(mfa.exception.detail, 'MFA required')
            # Client metadata cannot turn an ordinary activity into a teacher-owned syllabus.
            unrelated = native.Activity(name='Unrelated draft', org_id=1, course_id=10, activity_uuid='activity_unrelated',
                activity_type='TYPE_DYNAMIC', activity_sub_type='SUBTYPE_DYNAMIC_PAGE', extra_metadata=new.extra_metadata)
            db.add(unrelated); await db.commit()
            with self.assertRaises(HTTPException) as unrelated_denial:
                await get_editor_bootstrap(activity_request(unrelated.activity_uuid, '/editor-bootstrap'), unrelated.activity_uuid, teacher, db)
            self.assertEqual(unrelated_denial.exception.status_code, 403)
            # Reuse cannot offer that unbound tagged activity as an unopenable syllabus either.
            new.extra_metadata = {**new.extra_metadata, 'route66_syllabus': {
                **new.extra_metadata['route66_syllabus'], 'program': 'Moved synthetic program'}}
            db.add(new); await db.commit()
            with patch('src.services.courses.chapters.index_course'), patch('src.services.courses.activities.activities.index_activity'):
                recovered = await self.client.post(path, json={**body, 'expected_version': 1})
            self.assertEqual((recovered.status_code, recovered.json()['created']), (200, True))
            self.assertNotIn(recovered.json()['activity_uuid'], (unrelated.activity_uuid, new.activity_uuid))
            # Revocation is fresh; neither a role nor a persistent native author grant was added.
            assignment = (await db.exec(select(TeachingAssignment).where(TeachingAssignment.course_id == 10, TeachingAssignment.user_id == 2))).one()
            assignment.active = False; db.add(assignment); await db.commit()
            with self.assertRaises(HTTPException) as revoked:
                await get_editor_bootstrap(activity_request(new.activity_uuid, '/editor-bootstrap'), new.activity_uuid, teacher, db)
            self.assertEqual(revoked.exception.status_code, 403)
            assignment.active = True; db.add(assignment)
            member = (await db.exec(select(UserOrganization).where(UserOrganization.user_id == 2, UserOrganization.org_id == 1))).one()
            await db.delete(member); await db.commit()
            with self.assertRaises(HTTPException) as removed_member:
                await get_editor_bootstrap(activity_request(new.activity_uuid, '/editor-bootstrap'), new.activity_uuid, teacher, db)
            self.assertEqual(removed_member.exception.status_code, 403)
            self.assertEqual((await db.exec(select(ResourceAuthor))).all(), [])


def static_scope():
    """The calendar feature does not import native assignment/grading modules."""
    root = Path(__file__).resolve().parents[2]
    files = [root / 'routers/school_calendars.py', root / 'services/school_calendar.py', root / 'services/calendar_plan.py']
    return [f for f in files if 'assignment' in f.read_text().replace('TeachingAssignment', '')]

class ScopeTests(__import__('unittest').TestCase):
    def test_no_native_assignment_integration(self):
        self.assertEqual(static_scope(), [])


__all__ = [name for name in globals() if not name.startswith("__")]
