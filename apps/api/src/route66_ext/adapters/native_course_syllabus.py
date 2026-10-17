"""Create ordinary unpublished LearnHouse content through native services and permissions."""
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.courses.activities import Activity, ActivityCreate, ActivityTypeEnum, ActivitySubTypeEnum
from src.db.courses.chapters import Chapter, ChapterCreate
from src.security.rbac import check_resource_access, AccessAction
from src.services.courses.chapters import create_chapter
from src.services.courses.activities.activities import create_activity


async def prepare(db, request, user, course, year, semester, content, provenance, th=False):
    # Native service commits release savepoints; the caller keeps one atomic transaction and roster lock.
    async with AsyncSession(bind=await db.connection(), join_transaction_mode='create_savepoint', expire_on_commit=False) as native:
        return await _prepare(native, request, user, course, year, semester, content, provenance, th)


async def _prepare(db, request, user, course, year, semester, content, provenance, th):
    # Managing a registrar class does not grant native authoring permission.
    for action in (AccessAction.READ, AccessAction.CREATE, AccessAction.UPDATE):
        await check_resource_access(request, db, user, course.course_uuid, action)
    key = {'academic_year': year, 'semester': semester, 'program': provenance['program']}
    rows = (await db.exec(select(Activity.activity_uuid, Activity.extra_metadata).where(
        Activity.course_id == course.id, Activity.org_id == course.org_id))).all()
    for activity_uuid, metadata in rows:
        saved = (metadata or {}).get('route66_syllabus', {})
        if all(saved.get(k) == v for k, v in key.items()):
            return {'activity_uuid': activity_uuid, 'created': False}
    chapters = (await db.exec(select(Chapter).where(Chapter.course_id == course.id, Chapter.org_id == course.org_id))).all()
    chapter = next((c for c in chapters if (c.extra_metadata or {}).get('route66_syllabus') is True), None)
    if chapter is None:
        chapter = await create_chapter(request, ChapterCreate(name='ประมวลรายวิชา' if th else 'Course syllabus',
            course_id=course.id, org_id=course.org_id, extra_metadata={'route66_syllabus': True}), user, db)
    activity = await create_activity(request, ActivityCreate(chapter_id=chapter.id,
        name=f'{"ประมวลรายวิชา" if th else "Course syllabus"} · {semester}/{year} · {key["program"]}',
        activity_type=ActivityTypeEnum.TYPE_DYNAMIC, activity_sub_type=ActivitySubTypeEnum.SUBTYPE_DYNAMIC_PAGE,
        content=content, published=False, extra_metadata={'route66_syllabus': {**key, **provenance}}), user, db)
    return {'activity_uuid': activity.activity_uuid, 'created': True}
