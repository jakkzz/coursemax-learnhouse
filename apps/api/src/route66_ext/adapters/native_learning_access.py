"""Bounded native UserGroup access operations; caller owns the transaction.

Never creates groups, courses, accounts, roles, trails or runs. Never commits,
resets progress, publishes content, mints credentials or dispatches messages.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import delete
from sqlmodel import select

from src.db.courses.courses import Course
from src.db.usergroups import UserGroup
from src.db.usergroup_resources import UserGroupResource
from src.db.usergroup_user import UserGroupUser
from src.db.user_organizations import UserOrganization
from src.db.users import User
from src.security.features_utils.plan_check import check_org_plan
from src.security.org_auth import require_org_role_permission


def review():
    raise HTTPException(409, "Learning access changed. Ask an administrator to review the dedicated course group.")


async def authorize_configuration(db, actor_id: int, org_id: int):
    actor = await db.get(User, actor_id)
    if actor is None or actor.is_superadmin is not True:
        raise HTTPException(403, "Platform administrator approval required for learning access")
    await require_org_role_permission(actor_id, org_id, db, "usergroups", "action_update")
    await check_org_plan(org_id, "standard", "User Groups", db)


async def inspect_group(db, course_id: int, org_id: int, group_id: int, *, lock=False):
    query = select(Course).where(Course.id == course_id, Course.org_id == org_id)
    course = (await db.exec(query.with_for_update() if lock else query)).one_or_none()
    query = select(UserGroup).where(UserGroup.id == group_id, UserGroup.org_id == org_id)
    group = (await db.exec(query.with_for_update() if lock else query)).one_or_none()
    if course is None or group is None:
        raise HTTPException(404, "Course or dedicated native group not found")
    if course.public is not False:
        raise HTTPException(409, "Use a private course; this bridge never changes course visibility")
    if not course.course_uuid.startswith("course_") or not group.usergroup_uuid.startswith("usergroup_"):
        review()
    # Native resource links use UUIDs, not numeric IDs. Count every candidate
    # before treating a selected ID as authoritative, including other orgs.
    courses = (await db.exec(select(Course.id).where(Course.course_uuid == course.course_uuid))).all()
    groups = (await db.exec(select(UserGroup.id).where(UserGroup.usergroup_uuid == group.usergroup_uuid))).all()
    if courses != [course_id] or groups != [group_id]:
        review()
    links = (await db.exec(select(UserGroupResource).where(UserGroupResource.usergroup_id == group_id))).all()
    if (len(links) != 1 or links[0].resource_uuid != course.course_uuid or links[0].org_id != org_id):
        review()
    rows = (await db.exec(select(UserGroupUser).where(UserGroupUser.usergroup_id == group_id)
                          .order_by(UserGroupUser.id))).all()
    if any(row.org_id != org_id for row in rows):
        review()
    return {"group_id": group_id, "group_uuid": group.usergroup_uuid,
            "course_uuid": course.course_uuid, "published": bool(course.published),
            "members": [{"id": row.id, "user_id": row.user_id, "creation_date": row.creation_date} for row in rows]}


async def organization_users(db, org_id: int, user_ids: set[int]) -> set[int]:
    if not user_ids:
        return set()
    return set((await db.exec(select(User.id).join(UserOrganization, UserOrganization.user_id == User.id)
        .where(UserOrganization.org_id == org_id, User.id.in_(user_ids)))).all())


async def apply_delta(db, org_id: int, group_id: int, delta: dict) -> list[dict]:
    # Native permission/plan was checked at explicit configuration. Automatic
    # refresh operates only inside that immutable, course-scoped delegation.
    # Honor the native feature entitlement on every refresh; never bypass it.
    await check_org_plan(org_id, "standard", "User Groups", db)
    changes = []
    for member in delta["remove_members"]:
        result = await db.execute(delete(UserGroupUser).where(
            UserGroupUser.id == member["id"], UserGroupUser.user_id == member["user_id"],
            UserGroupUser.creation_date == member["creation_date"],
            UserGroupUser.usergroup_id == group_id, UserGroupUser.org_id == org_id))
        if result.rowcount != 1:
            review()
        changes.append({"action": "removed", **member})
    for user_id in delta["add_user_ids"]:
        stamp = datetime.now(timezone.utc).isoformat()
        row = UserGroupUser(usergroup_id=group_id, user_id=user_id, org_id=org_id,
                            creation_date=stamp, update_date=stamp)
        db.add(row)
        await db.flush()
        changes.append({"action": "added", "id": row.id, "user_id": user_id, "creation_date": stamp})
    return changes
