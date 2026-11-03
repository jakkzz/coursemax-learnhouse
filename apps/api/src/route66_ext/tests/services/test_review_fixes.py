"""Review regressions: disposable PostgreSQL, fictional rows, no provider traffic."""
import asyncio
from contextlib import ExitStack, asynccontextmanager
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI, HTTPException, Response
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.route66_ext.tests.services.test_academic_rosters import AcademicRosterTests
from src.route66_ext.adapters import native_learning_access_test_support as native
from src.route66_ext.adapters.application import install_retention
from src.route66_ext.routers import academic_classes as api
from src.route66_ext.services import academic_rosters as roster
from src.route66_ext.db.academic_classes import AcademicClass, AcademicRosterEntry


class ReviewFixTests(AcademicRosterTests):
    async def preview_patches(self, db, fetch):
        store = self.preview_store = {}

        class Redis:
            async def set(self, key, value, **kwargs): store[key] = value
            async def get(self, key): return store.get(key)
            async def eval(self, script, count, key, raw):
                if store.get(key) != raw: return 0
                del store[key]
                return 1

        @asynccontextmanager
        async def resources(config): yield Redis(), None

        return [*await self.endpoint_context(db), patch.object(api, 'resources', resources),
                patch.object(roster, 'fetch_roster', fetch)]

    async def test_preview_rejects_class_correction_during_fetch(self):
        async def fetch(cls):
            self.assertEqual(cls.section, 'P1')
            async with self.sessions() as other:
                await api.correct(20, api.Correction(course_id=10, academic_year=2569,
                    semester=1, section='P2', registry_course_id='100', registry_class_id='201',
                    expected_version=0, reason='Synthetic section correction'), None, Response(), other)
            return self.rows('6900000001'), 'a' * 64

        async with self.sessions() as db:
            with ExitStack() as stack:
                for item in await self.preview_patches(db, fetch): stack.enter_context(item)
                with self.assertRaises(HTTPException) as denied:
                    await api.preview(20, None, Response(), db)
                self.assertEqual(denied.exception.status_code, 409)
        self.assertEqual(self.preview_store, {})
        async with self.sessions() as db:
            self.assertEqual((await db.get(AcademicClass, 20)).section, 'P2')
            self.assertEqual(list((await db.exec(select(AcademicRosterEntry))).all()), [])

    async def test_unchanged_preview_applies_and_stale_apply_is_rejected(self):
        async with self.sessions() as db:
            with ExitStack() as stack:
                for item in await self.preview_patches(db, AsyncMock(return_value=(self.rows('6900000001'), 'b' * 64))):
                    stack.enter_context(item)
                first = await api.preview(20, None, Response(), db)
                second = await api.preview(20, None, Response(), db)
                result = await api.apply(20, api.Apply(preview_id=first['preview_id'], confirm_changes=True), None, Response(), db)
                self.assertTrue(result['applied'])
                with self.assertRaises(HTTPException) as denied:
                    await api.apply(20, api.Apply(preview_id=second['preview_id'], confirm_changes=True), None, Response(), db)
                self.assertEqual(denied.exception.status_code, 409)
        async with self.sessions() as db:
            self.assertEqual(len((await db.exec(select(AcademicRosterEntry))).all()), 1)

    async def content_fixture(self):
        async with self.engine.begin() as conn:
            for model in (native.Chapter, native.Activity, native.CourseChapter, native.ChapterActivity):
                await conn.run_sync(model.__table__.create)
        async with self.sessions.begin() as db:
            for ident in (1, 2):
                db.add(native.Chapter(id=ident, name=f'Fixture {ident}', course_id=10, org_id=1))
            db.add(native.Activity(id=1, activity_uuid='activity_fixture', name='Fixture', course_id=10, org_id=1,
                activity_type='TYPE_DYNAMIC', activity_sub_type='SUBTYPE_DYNAMIC_PAGE'))
            await db.flush()
            for ident in (1, 2):
                db.add(native.CourseChapter(chapter_id=ident, course_id=10, org_id=1, order=ident,
                    creation_date='fixture', update_date='fixture'))
            db.add(native.ChapterActivity(chapter_id=1, activity_id=1, course_id=10, org_id=1,
                order=0, creation_date='fixture', update_date='fixture'))

    async def links(self):
        async with self.sessions() as db:
            chapters = list((await db.exec(select(native.CourseChapter.chapter_id, native.CourseChapter.order)
                .order_by(native.CourseChapter.chapter_id))).all())
            activities = list((await db.exec(select(native.ChapterActivity.chapter_id, native.ChapterActivity.activity_id,
                native.ChapterActivity.order).order_by(native.ChapterActivity.id))).all())
            return chapters, activities

    async def test_invalid_reorder_rolls_back_chapter_and_activity_links(self):
        await self.content_fixture()
        before = await self.links()
        body = native.ChapterUpdateOrder.model_validate({'chapter_order_by_ids': [
            {'chapter_id': 1, 'activities_order_by_ids': [{'activity_id': 999}]}]})
        with patch.object(native.chapter_service, 'check_resource_access', AsyncMock()), \
             patch.object(native.chapter_service, 'enqueue_course', AsyncMock()):
            async with self.sessions() as db:
                with self.assertRaises(HTTPException) as denied:
                    await native.chapter_service.reorder_chapters_and_activities(None, 'course_fixture_10', body, None, db)
                self.assertEqual(denied.exception.status_code, 400)
            self.assertEqual(await self.links(), before)

    async def test_denied_reorder_never_takes_academic_lock(self):
        await self.content_fixture()
        before = await self.links()
        body = native.ChapterUpdateOrder(chapter_order_by_ids=[])
        with patch.object(native.chapter_service, 'check_resource_access', AsyncMock(side_effect=HTTPException(403, 'Denied'))), \
             patch.object(roster, 'serialize', AsyncMock()) as lock:
            async with self.sessions() as db:
                with self.assertRaises(HTTPException) as denied:
                    await native.chapter_service.reorder_chapters_and_activities(None, 'course_fixture_10', body, None, db)
                self.assertEqual(denied.exception.status_code, 403)
            lock.assert_not_awaited()
        self.assertEqual(await self.links(), before)

    async def test_reordering_completes_with_one_connection_and_concurrent_requests(self):
        await self.content_fixture()
        engine = create_async_engine(self.engine.url, connect_args={'host': '/scratch',
            'server_settings': {'search_path': self.schema}}, pool_size=1, max_overflow=0, pool_timeout=1)
        sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        app = FastAPI()
        app.include_router(native.chapter_router, prefix='/api/v1/chapters')

        async def database():
            async with sessions() as db: yield db

        app.dependency_overrides[native.get_db_session] = database
        app.dependency_overrides[native.get_current_user] = lambda: native.PublicUser(
            id=1, username='fixture', first_name='Synthetic', last_name='Fixture',
            email='fixture@example.com', user_uuid='user_fixture_1')
        install_retention(app)
        body = {'chapter_order_by_ids': [{'chapter_id': 2, 'activities_order_by_ids': [{'activity_id': 1}]},
                                         {'chapter_id': 1, 'activities_order_by_ids': []}]}
        try:
            with patch.object(native.chapter_service, 'check_resource_access', AsyncMock()), \
                 patch.object(native.chapter_service, 'enqueue_course', AsyncMock()):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://learn.example.com') as client:
                    results = await asyncio.wait_for(asyncio.gather(*(client.put(
                        '/api/v1/chapters/course/course_fixture_10/order', json=body) for _ in range(6)), return_exceptions=True), 10)
                    self.assertTrue(all(getattr(r, 'status_code', None) == 200 for r in results),
                                    [getattr(r, 'text', str(r)) for r in results])
            self.assertEqual(await self.links(), ([(1, 1), (2, 0)], [(2, 1, 0)]))
        finally:
            await engine.dispose()
