"""Create ordinary unpublished LearnHouse content through native services and permissions."""
import re
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.courses.activities import Activity, ActivityCreate, ActivityTypeEnum, ActivitySubTypeEnum
from src.db.courses.chapters import Chapter, ChapterCreate
from src.db.courses.courses import Course
from src.db.user_organizations import UserOrganization
from src.db.users import PublicUser
from src.route66_ext.db.academic_classes import AcademicClass, AcademicClassEvent, TeachingAssignment
from src.security.rbac import check_resource_access, AccessAction
from src.services.courses.chapters import create_chapter
from src.services.courses.activities.activities import create_activity


async def teacher_syllabus_access(request, db, user, resource_uuid, action):
    """Explicit assigned-teacher authority for syllabus creation and its bound activity only."""
    if not isinstance(user, PublicUser) or action not in (AccessAction.READ, AccessAction.CREATE, AccessAction.UPDATE):
        return False
    path = request.url.path
    if not isinstance(path, str):
        return False
    creation = re.fullmatch(r'/api/v1/school-calendars/schedules/by-class/([1-9][0-9]*)/syllabus', path)
    activity_path = re.fullmatch(r'/api/v1/activities/(activity_[^/]+)(?:/(?:editor-bootstrap|state|versions(?:/[0-9]+(?:/restore)?)?))?', path)
    if not creation and (not activity_path or action == AccessAction.CREATE):
        return False
    course = (await db.exec(select(Course).where(Course.course_uuid == resource_uuid))).one_or_none()
    if course is None:
        return False
    member = (await db.exec(select(UserOrganization).where(UserOrganization.user_id == user.id,
        UserOrganization.org_id == course.org_id))).first()
    assigned = (await db.exec(select(TeachingAssignment).where(TeachingAssignment.user_id == user.id,
        TeachingAssignment.course_id == course.id, TeachingAssignment.active == True))).first()
    if member is None or assigned is None:
        return False
    if creation:
        cls = await db.get(AcademicClass, int(creation[1]))
        return bool(cls and cls.course_id == course.id and cls.org_id in (None, course.org_id))
    activity = (await db.exec(select(Activity).where(Activity.activity_uuid == activity_path[1],
        Activity.course_id == course.id, Activity.org_id == course.org_id))).one_or_none()
    if activity is None:
        return False
    # Immutable preparation evidence, not client-editable activity metadata, owns this grant.
    evidence = (await db.exec(select(AcademicClassEvent).where(
        AcademicClassEvent.kind == 'class_syllabus_prepared',
        AcademicClassEvent.details['activity_uuid'].astext == activity.activity_uuid,
        AcademicClassEvent.details['course_id'].astext == str(course.id)))).first()
    return evidence is not None


async def prepare(db, request, user, course, year, semester, content, provenance, th=False):
    # Native service commits release savepoints; the caller keeps one atomic transaction and roster lock.
    async with AsyncSession(bind=await db.connection(), join_transaction_mode='create_savepoint', expire_on_commit=False) as native:
        return await _prepare(native, request, user, course, year, semester, content, provenance, th)


async def _prepare(db, request, user, course, year, semester, content, provenance, th):
    # Native policy includes only the reviewed assigned-teacher syllabus capability.
    for action in (AccessAction.READ, AccessAction.CREATE, AccessAction.UPDATE):
        await check_resource_access(request, db, user, course.course_uuid, action)
    key = {'academic_year': year, 'semester': semester, 'program': provenance['program']}
    prepared = select(AcademicClassEvent.details['activity_uuid'].astext).where(
        AcademicClassEvent.kind == 'class_syllabus_prepared',
        AcademicClassEvent.details['course_id'].astext == str(course.id))
    rows = (await db.exec(select(Activity.activity_uuid, Activity.extra_metadata).where(
        Activity.course_id == course.id, Activity.org_id == course.org_id,
        Activity.activity_uuid.in_(prepared)))).all()
    for activity_uuid, metadata in rows:
        saved = (metadata or {}).get('route66_syllabus', {})
        if all(saved.get(k) == v for k, v in key.items()):
            return {'activity_uuid': activity_uuid, 'created': False}
    if callable(content):
        content = await content()  # Reopening authored content must not depend on a new school fetch.
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
