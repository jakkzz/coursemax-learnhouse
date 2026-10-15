"""Isolate optional learning-access failures from verified identity/roster commits.

Never grants on failure. Withdraw only exact, still-live bridge-owned rows; leave
manual/recreated rows and unrelated course access alone. Retry is ordinary UI work.
"""
import logging
from sqlmodel import select

log = logging.getLogger(__name__)
from src.route66_ext.db.academic_classes import AcademicClassEvent
from src.route66_ext.adapters import native_learning_access as native


async def release(db, actor_id, course_id, binding):
    if binding is None:
        return 0
    rows = (await db.exec(select(AcademicClassEvent).where(
        AcademicClassEvent.kind == "learning_access_membership").order_by(AcademicClassEvent.id))).all()
    from src.route66_ext.services import learning_access as access
    authorizations = {r.id: r for r in (await db.exec(select(AcademicClassEvent).where(
        AcademicClassEvent.kind == "learning_access_configured"))).all()}
    owned = set()
    for event in rows:
        d = event.details
        if not access._receipt_authorized(event, authorizations):
            continue
        authorization = authorizations[d["authorization_event_id"]]
        if (d.get("course_id") != course_id or d.get("group_id") != binding["group_id"]
            or authorization.details.get("group_uuid") != binding["group_uuid"]
            or authorization.details.get("org_id") != binding["org_id"]):
            continue
        member = d.get("membership", {})
        if not isinstance(member, dict): continue
        key = (member.get("id"), member.get("user_id"), member.get("creation_date"))
        if type(key[0]) is not int or key[0] <= 0 or type(key[1]) is not int or key[1] <= 0 or not isinstance(key[2], str) or not key[2]:
            continue
        if member.get("action") == "added": owned.add(key)
        elif member.get("action") == "removed": owned.discard(key)
    changes = await native.release_owned(db, binding, owned)
    for change in changes:
        db.add(AcademicClassEvent(actor_user_id=actor_id, kind="learning_access_membership",
            details={"course_id": course_id, "group_id": binding["group_id"], "membership": change,
                     "authorization_event_id": binding["event_id"], "trigger": "access_recovery"}))
    await db.flush()
    return len(changes)


async def reconcile(db, actor_id, course_id):
    from src.route66_ext.services import learning_access as access
    binding = None
    try:
        async with db.begin_nested():
            binding = await access._binding(db, course_id)
            if binding is None or binding["enabled"] is not True:
                return {"status": "not_configured", "removed_count": 0}
            counts = await access._sync(db, actor_id, course_id, binding["org_id"], binding)
            # Completion is evidence too, so the UI can clear a previous repair task.
            db.add(AcademicClassEvent(actor_user_id=actor_id, kind="learning_access_ready",
                details={"course_id": course_id, "authorization_event_id": binding["event_id"]}))
            await db.flush()
            return {"status": "ready", **counts}
    except Exception:
        log.warning("Native learning access needs repair for course %s", course_id, exc_info=True)
        # A native licensing/configuration error must never undo fresh Google
        # evidence or an accepted roster. No new grants are made on this branch.
        async with db.begin_nested():
            removed = await release(db, actor_id, course_id, binding)
            db.add(AcademicClassEvent(actor_user_id=actor_id, kind="learning_access_pending",
                details={"course_id": course_id, "reason": "native_access_needs_repair",
                         "removed_owned_count": removed,
                         "authorization_event_id": binding["event_id"] if binding else None}))
            await db.flush()
        return {"status": "needs_repair", "removed_count": removed}
