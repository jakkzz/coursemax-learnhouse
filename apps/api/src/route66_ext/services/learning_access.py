"""Reviewed institutional eligibility -> native private-course read membership.

Existing AcademicClassEvent is append-only configuration/provenance/receipt storage.
No new schema, second login, native enrollment writer or progress mutation.
"""
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import or_
from sqlmodel import select

from src.route66_ext.adapters import native_learning_access as native
from src.route66_ext.db.academic_classes import (
    AcademicClass, AcademicRosterEntry, SchoolStudent, AcademicClassEvent, CourseRegistryBinding, TeachingAssignment,
)
from src.route66_ext.db.school_identity import SchoolGoogleEvidence
from src.route66_ext.db.provider_identity import ProviderIdentity
from src.route66_ext.services import academic_rosters as roster
from src.route66_ext.services.learning_access_policy import membership_delta

_CONFIG = "learning_access_configured"
_MEMBER = "learning_access_membership"
_APPLIED = "learning_access_applied"


def _positive(value):
    return type(value) is int and value > 0


def _receipt_authorized(row, configurations):
    d = row.details
    if (not isinstance(d, dict) or not _positive(d.get("authorization_event_id"))
            or not _positive(d.get("course_id")) or not _positive(d.get("group_id"))):
        return False
    authorization = configurations.get(d["authorization_event_id"])
    if authorization is None or authorization.id >= row.id:
        return False
    a = authorization.details
    return (authorization.kind == _CONFIG and isinstance(a, dict)
            and a.get("course_id") == d.get("course_id") and a.get("group_id") == d.get("group_id")
            and (row.class_id is None or row.class_id == authorization.class_id))


async def _events(db, kind, course_id=None):
    # Validate before filtering. SQL JSON-to-int casts or filtering malformed
    # course IDs first could hide broken provenance or fail with an opaque 500.
    rows = (await db.exec(select(AcademicClassEvent).where(
        AcademicClassEvent.kind == kind).order_by(AcademicClassEvent.id))).all()
    authorizations = {r.id: r for r in (await db.exec(select(AcademicClassEvent).where(
        AcademicClassEvent.kind == _CONFIG))).all()} if kind == _MEMBER else {}
    for row in rows:
        details = row.details
        if not isinstance(details, dict) or not _positive(details.get("course_id")):
            native.review()
        if kind == _CONFIG:
            if (not _positive(details.get("org_id")) or not _positive(details.get("group_id"))
                    or not isinstance(details.get("group_uuid"), str) or not details["group_uuid"]
                    or type(details.get("enabled")) is not bool
                    or not isinstance(details.get("reason"), str) or len(details["reason"].strip()) < 5
                    or not _positive(row.class_id)):
                native.review()
            cls = await db.get(AcademicClass, row.class_id)
            if cls is None or cls.course_id != details["course_id"]:
                native.review()
        elif kind == _MEMBER:
            if not _positive(details.get("group_id")) or not _receipt_authorized(row, authorizations):
                native.review()
            try:
                membership_delta([], [], [details.get("membership")])
            except ValueError:
                native.review()
    return [row for row in rows if course_id is None or row.details["course_id"] == course_id]


async def _binding(db, course_id):
    rows = await _events(db, _CONFIG, course_id)
    if not rows:
        return None
    previous = rows[0]
    for row in rows[1:]:
        old = tuple(previous.details[k] for k in ("group_id", "group_uuid", "org_id"))
        new = tuple(row.details[k] for k in ("group_id", "group_uuid", "org_id"))
        if old != new and (row.details.get("previous_event_id") != previous.id
                          or row.details["org_id"] != previous.details["org_id"]):
            native.review()
        previous = row
    return {**previous.details, "event_id": previous.id}


def _event(db, actor_id, kind, course_id, details, cls=None):
    roster.event(db, actor_id, kind, {"course_id": course_id, **details}, cls)


async def _eligibility(db, course_id, org_id, *, include_teachers=True):
    classes = (await db.exec(select(AcademicClass).where(AcademicClass.course_id == course_id)
                             .order_by(AcademicClass.id))).all()
    binding = await db.get(CourseRegistryBinding, course_id)
    if not binding or any(c.registry_course_id != binding.registry_course_id for c in classes):
        native.review()
    pairs = (await db.exec(select(AcademicRosterEntry, SchoolStudent).join(
        SchoolStudent, SchoolStudent.id == AcademicRosterEntry.student_id).join(
        AcademicClass, AcademicClass.id == AcademicRosterEntry.class_id).where(
        AcademicClass.course_id == course_id).order_by(AcademicRosterEntry.id))).all()
    proofs = (await db.exec(select(SchoolGoogleEvidence).join(ProviderIdentity,
        ProviderIdentity.id == SchoolGoogleEvidence.identity_id).where(
        ProviderIdentity.provider == "google", ProviderIdentity.retired_at.is_(None),
        ProviderIdentity.user_id == SchoolGoogleEvidence.user_id))).all()
    proof_users = {e.user_id for e in proofs}
    claims = await roster.active_claims(db)
    teachers = (await db.exec(select(TeachingAssignment).where(TeachingAssignment.course_id == course_id)
                              .order_by(TeachingAssignment.id))).all()
    teacher_ids = {t.user_id for t in teachers if t.active and include_teachers}
    candidates, waiting, conflicts = teacher_ids & proof_users, 0, 0
    for entry, profile in pairs:
        if entry.status != "active":
            continue
        if profile.user_id is None or profile.user_id not in proof_users:
            waiting += 1
            continue
        if entry.source == "manual":
            candidates.add(profile.user_id)
        elif (profile.has_registry_evidence and profile.student_number
              and set(claims.get(profile.student_number, {})) == {profile.user_id}):
            candidates.add(profile.user_id)
        else:
            conflicts += 1
    eligible = await native.organization_users(db, org_id, candidates)
    return sorted(eligible), {
        "classes": [(c.id, c.version) for c in classes],
        "teachers": [(t.id, t.user_id, t.active) for t in teachers],
        "proofs": sorted((e.user_id, e.identity_id) for e in proofs if e.user_id in candidates),
        "registry_course_id": binding.registry_course_id,
        "waiting_count": waiting + len(candidates - eligible), "conflict_count": conflicts,
    }


async def _state(db, course_id, org_id, group_id, enabled, *, lock=False, include_teachers=None):
    binding = await _binding(db, course_id)
    info = await native.inspect_group(db, course_id, org_id, group_id, lock=lock)
    if binding:
        if (binding["org_id"], binding["group_id"], binding["group_uuid"]) != (org_id, group_id, info["group_uuid"]):
            native.review()
    elif info["members"]:
        raise HTTPException(409, "First activation requires an empty dedicated native group linked only to this course")
    for event in await _events(db, _CONFIG):
        if event.details["group_id"] == group_id and event.details["course_id"] != course_id:
            native.review()
    if include_teachers is None:
        include_teachers = binding is None or binding.get("eligibility_policy") == "students_and_assigned_teachers"
    eligible, facts = await _eligibility(db, course_id, org_id, include_teachers=include_teachers)
    events = await _events(db, _MEMBER, course_id)
    reserved = {row.details["group_id"] for row in await _events(db, _CONFIG, course_id)}
    if any(row.details["group_id"] not in reserved for row in events):
        native.review()
    receipts = [row.details["membership"] for row in events if row.details["group_id"] == group_id]
    try:
        delta = membership_delta(eligible if enabled else [], info["members"], receipts)
    except ValueError:
        native.review()
    state = {"binding": binding, "group": info, "facts": facts, "eligible": eligible,
             "delta": delta, "enabled": enabled, "org_id": org_id, "course_id": course_id}
    return state


async def _configuration_state(db, course_id, org_id, group_id, enabled, replace_group=False, lock=False):
    binding = await _binding(db, course_id)
    if group_id is None and binding and not replace_group:
        group_id = binding["group_id"]
    if group_id is not None:
        return await _state(db, course_id, org_id, group_id, enabled, lock=lock, include_teachers=True)
    info = await native.provision_state(db, course_id, org_id)
    eligible, facts = await _eligibility(db, course_id, org_id)
    return {"binding": binding, "group": info, "facts": facts, "eligible": eligible,
            "delta": membership_delta(eligible if enabled else [], [], []),
            "enabled": enabled, "org_id": org_id, "course_id": course_id}


def _preview(state, actor_id):
    fingerprint = hashlib.sha256(json.dumps({"actor_id": actor_id, **state},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    delta = state["delta"]
    return {"course_id": state["course_id"], "group_id": state["group"]["group_id"],
            "enabled": state["enabled"], "expected_fingerprint": fingerprint,
            "eligible_count": len(state["eligible"]), "add_count": len(delta["add_user_ids"]),
            "remove_count": len(delta["remove_members"]),
            "preserved_manual_count": delta["preserved_manual_count"],
            "waiting_count": state["facts"]["waiting_count"],
            "conflict_count": state["facts"]["conflict_count"],
            "course_published": state["group"]["published"],
            "native_enrollment_changed": False, "progress_changed": False,
            "will_create_group": state["group"]["group_id"] is None,
            "restricts_org_wide_access": state["group"].get("restricts_org_wide_access", False)}


async def preview(db, actor_id, cls, org_id, group_id=None, enabled=True, replace_group=False):
    await roster.serialize(db)
    await db.refresh(cls)
    await native.authorize_configuration(db, actor_id, org_id)
    return _preview(await _configuration_state(db, cls.course_id, org_id, group_id, enabled, replace_group), actor_id)


async def _sync(db, actor_id, course_id, org_id, binding):
    state = await _state(db, course_id, org_id, binding["group_id"], binding["enabled"], lock=True)
    changes = await native.apply_delta(db, org_id, binding["group_id"], state["delta"])
    for change in changes:
        _event(db, actor_id, _MEMBER, course_id, {"group_id": binding["group_id"], "membership": change,
            "authorization_event_id": binding["event_id"], "trigger": "configured_roster_reconciliation"})
    await db.flush()
    return {"added_count": sum(c["action"] == "added" for c in changes),
            "removed_count": sum(c["action"] == "removed" for c in changes),
            "preserved_manual_count": state["delta"]["preserved_manual_count"],
            "native_enrollment_changed": False, "progress_changed": False}


async def apply(db, actor_id, cls, org_id, *, group_id=None, enabled=True, expected_fingerprint, request_id, reason, replace_group=False):
    await roster.serialize(db)
    await db.refresh(cls)
    await native.authorize_configuration(db, actor_id, org_id)
    body = {"actor_id": actor_id, "class_id": cls.id, "org_id": org_id, "group_id": group_id,
            "enabled": enabled, "expected_fingerprint": expected_fingerprint, "reason": reason,
            "replace_group": replace_group}
    body_hash = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    previous = (await db.exec(select(AcademicClassEvent).where(
        AcademicClassEvent.kind == _APPLIED,
        AcademicClassEvent.details["request_id"].as_string() == request_id))).all()
    if previous:
        if len(previous) != 1 or previous[0].details.get("body_hash") != body_hash:
            raise HTTPException(409, "This request identifier is already used; request a new preview")
        result = previous[0].details.get("result")
        if not isinstance(result, dict) or result.get("applied") is not True:
            native.review()
        return {**result, "replayed": True}
    async with db.begin_nested():
        state = await _configuration_state(db, cls.course_id, org_id, group_id, enabled, replace_group, lock=True)
        if _preview(state, actor_id)["expected_fingerprint"] != expected_fingerprint:
            raise HTTPException(409, "Eligibility or native access changed. Review a fresh preview")
        previous = state["binding"]
        if replace_group and previous:
            from src.route66_ext.services.learning_access_recovery import release
            await release(db, actor_id, cls.course_id, previous)
        if state["group"]["group_id"] is None:
            group_id = await native.provision_group(db, actor_id, cls.course_id, org_id)
            info = await native.inspect_group(db, cls.course_id, org_id, group_id, lock=True)
        else:
            info = state["group"]; group_id = info["group_id"]
        _event(db, actor_id, _CONFIG, cls.course_id, {
            "org_id": org_id, "group_id": group_id, "group_uuid": info["group_uuid"],
            "previous_event_id": previous["event_id"] if previous else None,
            "enabled": enabled, "reason": reason,
            "eligibility_policy": "students_and_assigned_teachers"}, cls)
        await db.flush()
        binding = await _binding(db, cls.course_id)
        result = {"applied": True, "enabled": enabled, **await _sync(db, actor_id, cls.course_id, org_id, binding)}
        _event(db, actor_id, "learning_access_ready", cls.course_id, {"authorization_event_id": binding["event_id"]}, cls)
        _event(db, actor_id, _APPLIED, cls.course_id, {"request_id": request_id, "body_hash": body_hash,
                                                   "result": result}, cls)
        await db.flush()
    return {**result, "replayed": False}


async def refresh_course(db, actor_id, course_id):
    """Caller already holds roster serialization; preserve its outer transaction."""
    from src.route66_ext.services.learning_access_recovery import reconcile
    return await reconcile(db, actor_id, course_id)


async def refresh_user(db, user_id):
    # Include withdrawn rows AND exact-number claims on another existing owner:
    # a new conflicting claimant must revoke the old managed grant, never claim it.
    claims = await roster.active_claims(db)
    numbers = {number for number, owners in claims.items() if user_id in owners}
    courses = set((await db.exec(select(AcademicClass.course_id).join(
        AcademicRosterEntry, AcademicRosterEntry.class_id == AcademicClass.id).join(
        SchoolStudent, SchoolStudent.id == AcademicRosterEntry.student_id).where(or_(
        SchoolStudent.user_id == user_id,
        SchoolStudent.student_number.in_(numbers or {""}))))).all())
    courses.update((await db.exec(select(TeachingAssignment.course_id).where(TeachingAssignment.user_id == user_id))).all())
    for course_id in sorted(courses):
        await refresh_course(db, user_id, course_id)
