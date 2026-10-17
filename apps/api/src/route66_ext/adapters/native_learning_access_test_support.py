"""Test-only native facades for isolated learning-access integration.

Not imported by runtime routes/services/bootstrap. Keeping native test seams here
preserves the extension's adapter import boundary; none supplies actor authority.
"""
from src.core.events.database import get_db_session
from src.db.usergroups import UserGroup
from src.db.usergroup_resources import UserGroupResource
from src.db.usergroup_user import UserGroupUser
from src.db.courses.courses import Course
from src.db.courses.chapters import Chapter
from src.db.courses.course_chapters import CourseChapter
from src.db.courses.chapter_activities import ChapterActivity
from src.db.courses.activities import Activity, ActivityTypeEnum, ActivitySubTypeEnum, ActivityUpdate
from src.db.courses.activity_versions import ActivityVersion
from src.db.resource_authors import ResourceAuthor
from src.db.user_organizations import UserOrganization
from src.db.trails import Trail
from src.db.trail_runs import TrailRun, StatusEnum
from src.db.trail_steps import TrailStep
from src.db.users import User, PublicUser, AnonymousUser
from src.db.organization_config import OrganizationConfig
from src.security.rbac import check_resource_access, AccessAction
from src.services.courses.activities.activities import get_activity as read_native_activity, update_activity, get_editor_bootstrap
from src.security.rbac.resource_access import ResourceAccessChecker


def native_courses_router():
    from src.routers.courses.courses import router
    return router
