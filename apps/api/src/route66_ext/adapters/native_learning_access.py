"""Bounded native UserGroup access operations; caller owns the transaction.

Provisions only a reviewed dedicated native group/link, under native create,
update, membership, Standard-plan and actual-row quota gates. Never creates
courses, accounts, roles, trails or runs; never commits, resets progress,
publishes content, mints credentials or dispatches messages.
"""
from datetime import datetime, timezone
from uuid import uuid4

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
from src.security.features_utils.usage import check_limits_with_usage
from src.security.rbac.resource_access import check_resource_access
from src.security.rbac.types import AccessAction


def review():
    raise HTTPException(409, "Course access changed. Review access repair in this class workspace; no new access was granted.")


async def can_read(db, request, user, course):
    if not course.published:
        return False
    decision = await check_resource_access(request, db, user, course.course_uuid, AccessAction.READ, raise_on_deny=False)
    return decision.allowed


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


async def provision_state(db, course_id, org_id):
    course = (await db.exec(select(Course).where(Course.id == course_id, Course.org_id == org_id))).one_or_none()
    if course is None: raise HTTPException(404, "Course not found")
    if course.public is not False:
        raise HTTPException(409, "Choose a private native course; its publication and visibility are not changed here")
    candidates = (await db.exec(select(Course.id).where(Course.course_uuid == course.course_uuid))).all()
    if candidates != [course_id] or not course.course_uuid.startswith("course_"): review()
    links = (await db.exec(select(UserGroupResource).where(
        UserGroupResource.resource_uuid == course.course_uuid).order_by(UserGroupResource.id))).all()
    return {"group_id": None, "group_uuid": None, "course_uuid": course.course_uuid,
            "course_name": course.name, "published": bool(course.published), "members": [],
            "existing_links": [(r.id, r.usergroup_id, r.org_id) for r in links],
            "restricts_org_wide_access": not links}


async def provision_group(db, actor_id, course_id, org_id):
    await authorize_configuration(db, actor_id, org_id)
    await require_org_role_permission(actor_id, org_id, db, "usergroups", "action_create")
    await check_limits_with_usage("usergroups", org_id, db)
    course = (await db.exec(select(Course).where(Course.id == course_id, Course.org_id == org_id).with_for_update())).one()
    state = await provision_state(db, course_id, org_id)
    stamp = datetime.now(timezone.utc).isoformat()
    group = UserGroup(org_id=org_id, name=("Class roster · " + course.name)[:200],
        description="Roster-owned access; manual memberships remain native-owned",
        usergroup_uuid="usergroup_" + str(uuid4()), creation_date=stamp, update_date=stamp)
    db.add(group); await db.flush()
    db.add(UserGroupResource(usergroup_id=group.id, org_id=org_id, resource_uuid=state["course_uuid"]))
    await db.flush()
    return group.id


async def release_owned(db, binding, keys):
    # Removal is not a paid-feature grant: native plan loss cannot strand stale
    # bridge permissions. Recheck ID/UUID; removal still scopes each row to its
    # ORIGINAL org. Group-org drift cannot strand our old-org grants or authorize
    # deletion of new-org/manual memberships. Recreated groups are not adopted.
    group = (await db.exec(select(UserGroup).where(UserGroup.id == binding["group_id"],
        UserGroup.usergroup_uuid == binding["group_uuid"]).with_for_update())).one_or_none()
    if group is None: return []
    changes = []
    for ident, user_id, created in sorted(keys):
        result = await db.execute(delete(UserGroupUser).where(UserGroupUser.id == ident,
            UserGroupUser.user_id == user_id, UserGroupUser.creation_date == created,
            UserGroupUser.usergroup_id == group.id, UserGroupUser.org_id == binding["org_id"]))
        if result.rowcount == 1:
            changes.append({"action": "removed", "id": ident, "user_id": user_id, "creation_date": created})
    return changes


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
