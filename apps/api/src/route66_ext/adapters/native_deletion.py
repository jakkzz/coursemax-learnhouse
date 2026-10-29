"""Read native deletion targets and permissions; never replace native deletion writers."""
from contextlib import asynccontextmanager

from sqlmodel import select
from src.core.events.database import get_db_session
from src.db.courses.activities import Activity
from src.db.courses.chapters import Chapter
from src.db.courses.chapter_activities import ChapterActivity
from src.db.courses.courses import Course
from src.security.auth import get_current_user as authenticate
from src.security.rbac import AccessAction, check_resource_access

session = asynccontextmanager(get_db_session)


async def deletion_targets(request, db, kind: str, identifier: int | str, user) -> list[str]:
    """Match native chapter/activity deletion, including shared-activity retention."""
    if kind == 'chapters':
        target = await db.get(Chapter, identifier)
    else:
        target = (await db.exec(select(Activity).where(Activity.activity_uuid == identifier))).first()
    if target is None:
        return []  # Native handler owns missing-target responses.
    course = await db.get(Course, target.course_id)
    if course is None:
        return []
    await check_resource_access(request, db, user, course.course_uuid, AccessAction.DELETE)
    if kind == 'activities':
        return [target.activity_uuid]
    linked = select(ChapterActivity.activity_id).where(ChapterActivity.chapter_id == target.id)
    elsewhere = select(ChapterActivity.activity_id).where(
        ChapterActivity.chapter_id != target.id, ChapterActivity.activity_id.in_(linked))
    return list((await db.exec(select(Activity.activity_uuid).where(
        Activity.course_id == course.id, Activity.id.in_(linked), Activity.id.not_in(elsewhere),
    ))).all())
