"""HTTP regressions using the calendar fixture's persisted, authored syllabus."""
import asyncio
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from sqlalchemy import text
from sqlmodel import select
from src.core.events.database import get_db_session
from src.db.courses.activities import Activity
from src.db.courses.activity_versions import ActivityVersion
from src.db.courses.chapters import Chapter
from src.db.courses.chapter_activities import ChapterActivity
from src.db.users import User
from src.db.custom_domains import CustomDomain
from src.routers.courses import chapters
from src.routers.courses.activities import activities
from src.security.auth import create_access_token
from src.route66_ext.adapters.application import install_retention
from src.route66_ext.db.academic_classes import AcademicClassEvent
from src.route66_ext.services.academic_rosters import serialize


async def check_native_deletion(case):
    app = FastAPI()
    app.include_router(chapters.router, prefix='/api/v1/chapters')
    app.include_router(activities.router, prefix='/api/v1/activities')

    async def database():
        async with case.sessions() as db:
            yield db

    app.dependency_overrides[get_db_session] = database
    install_retention(app, sessions=case.sessions)
    async with case.engine.begin() as conn:
        await conn.run_sync(CustomDomain.__table__.create)
    async with case.sessions.begin() as db:
        admin = await db.get(User, 1)
        admin.email_verified = True
        db.add(admin)
        token = create_access_token({'sub': admin.email, 'purpose': 'session', 'amr': 'password', 'sorg': 1})
        learner = await db.get(User, 3)
        learner.email_verified = True
        db.add(learner)
        learner_token = create_access_token({'sub': learner.email, 'purpose': 'session', 'amr': 'password', 'sorg': 1})
        protected_chapter = (await db.exec(select(Chapter).where(Chapter.course_id == 10))).first()
        protected = (await db.exec(select(ChapterActivity.activity_id).where(
            ChapterActivity.chapter_id == protected_chapter.id))).all()
        bound = await db.get(Activity, protected[0])
        versions = (await db.exec(select(ActivityVersion.id).where(ActivityVersion.activity_id.in_(protected)))).all()
        case.assertTrue(versions)
        events = (await db.exec(select(AcademicClassEvent.id).where(
            AcademicClassEvent.kind == 'class_syllabus_prepared'))).all()
        # Removing an extra chapter link must still work when the bound activity survives.
        ordinary = Chapter(name='Ordinary chapter', org_id=1, course_id=10)
        db.add(ordinary)
        await db.flush()
        db.add(ChapterActivity(chapter_id=ordinary.id, activity_id=bound.id, course_id=10,
                               org_id=1, order=0, creation_date='fixture', update_date='fixture'))
        for uuid in ('activity_ordinary_direct', 'activity_ordinary_chapter'):
            row = Activity(name='Ordinary draft', activity_uuid=uuid, course_id=10, org_id=1,
                           activity_type='TYPE_DYNAMIC', activity_sub_type='SUBTYPE_DYNAMIC_PAGE',
                           extra_metadata={'route66_syllabus': {'program': 'Fake client tag'}})
            db.add(row)
            await db.flush()
            db.add(ChapterActivity(chapter_id=ordinary.id, activity_id=row.id, course_id=10,
                                   org_id=1, order=1, creation_date='fixture', update_date='fixture'))
    origin = 'https://learn.example.com'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=origin,
                                 cookies={'LH_access': token}, headers={'Origin': origin}) as client:
        with patch('src.services.courses.transfer.storage_utils.delete_storage_directory') as files, \
             patch('src.core.events.database._async_session_factory', case.sessions), \
             patch('src.services.courses.chapters.enqueue_course', new=AsyncMock()):
            for path in (f'/api/v1/chapters/{protected_chapter.id}', f'/api/v1/activities/{bound.activity_uuid}',
                         f'/api/v1/chapters/{protected_chapter.id}/', f'/api/v1/activities/{bound.activity_uuid}/',
                         f'/api/v1/chapters/{protected_chapter.id}.0', f'/api/v1/chapters/+00{protected_chapter.id}'):
                result = await client.delete(path)
                case.assertEqual(result.status_code, 409, result.text)
                case.assertEqual(result.headers.get('access-control-allow-origin'), origin)
            denied = await client.delete(f'/api/v1/activities/{bound.activity_uuid}',
                                         headers={'Cookie': 'LH_access=' + learner_token})
            case.assertEqual(denied.status_code, 403, denied.text)
            anonymous = await client.delete(f'/api/v1/activities/{bound.activity_uuid}', headers={'Cookie': ''})
            case.assertIn(anonymous.status_code, (401, 403), anonymous.text)
            csrf = await client.delete(f'/api/v1/activities/{bound.activity_uuid}', headers={'Origin': 'https://evil.invalid'})
            case.assertEqual(csrf.status_code, 403, csrf.text)
            files.assert_not_called()
            case.assertEqual((await client.delete('/api/v1/chapters/not-an-int')).status_code, 422)
            case.assertEqual((await client.delete('/api/v1/chapters/999999')).status_code, 404)
            result = await client.delete('/api/v1/activities/activity_ordinary_direct')
            case.assertEqual(result.status_code, 200, result.text)
            # Pause after native commit to prove serialization spans the ENTIRE native call.
            committed, release, attempted = asyncio.Event(), asyncio.Event(), asyncio.Event()

            async def pause_after_commit(*args):
                committed.set()
                await release.wait()

            async def competing_preparation():
                async with case.sessions() as db:
                    attempted.set()
                    await serialize(db)
                    return await db.get(Activity, bound.id)

            ordering_attempted = asyncio.Event()

            async def guard_lock(db):
                if committed.is_set():
                    ordering_attempted.set()
                await serialize(db)

            competing = reordering = None
            with patch('src.services.courses.chapters.enqueue_course', new=pause_after_commit), \
                 patch('src.route66_ext.security.syllabus_retention.serialize', new=guard_lock):
                deleting = asyncio.create_task(client.delete(f'/api/v1/chapters/{ordinary.id}'))
                try:
                    await asyncio.wait_for(committed.wait(), 5)
                    competing = asyncio.create_task(competing_preparation())
                    await attempted.wait()
                    with case.assertRaises(TimeoutError):
                        await asyncio.wait_for(asyncio.shield(competing), 0.1)
                    reordering = asyncio.create_task(client.put('/api/v1/chapters/course/course_fixture_10/order',
                        json={'chapter_order_by_ids': [{'chapter_id': protected_chapter.id,
                            'activities_order_by_ids': [{'activity_id': ident} for ident in protected]}]}))
                    await asyncio.wait_for(ordering_attempted.wait(), 5)
                    case.assertFalse(reordering.done())
                finally:
                    release.set()
                    result = await asyncio.wait_for(deleting, 5)
                    if competing is not None:
                        case.assertIsNotNone(await asyncio.wait_for(competing, 5))
                    if reordering is not None:
                        reordered = await asyncio.wait_for(reordering, 5)
                        case.assertEqual(reordered.status_code, 200, reordered.text)
            case.assertEqual(result.status_code, 200, result.text)
            case.assertEqual(files.call_count, 2)
            case.assertEqual({call.args[0].rsplit('/', 1)[-1] for call in files.call_args_list},
                             {'activity_ordinary_direct', 'activity_ordinary_chapter'})
    async with case.sessions() as db:
        case.assertEqual(set((await db.exec(select(Activity.id).where(Activity.id.in_(protected)))).all()), set(protected))
        case.assertEqual(set((await db.exec(select(ActivityVersion.id).where(ActivityVersion.id.in_(versions)))).all()), set(versions))
        case.assertEqual(set((await db.exec(select(AcademicClassEvent.id).where(
            AcademicClassEvent.kind == 'class_syllabus_prepared'))).all()), set(events))
        case.assertIsNotNone(await db.get(Chapter, protected_chapter.id))
        case.assertIsNone(await db.get(Chapter, ordinary.id))
        # No request, including denied ones, left an advisory lock behind.
        case.assertTrue((await db.execute(text('SELECT pg_try_advisory_xact_lock(664466, 1)'))).scalar())
