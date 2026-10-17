"""One reviewed connection: official section, native course, teaching and access.

Assigned teachers reuse explicit course mappings for routine section setup.
New mappings and native access-policy changes use the existing administrator review.
"""
import asyncio
import hashlib
import json
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.route66_ext.adapters.core_events_database import get_db_session
from src.route66_ext.adapters.db_courses_courses import Course
from src.route66_ext.adapters.db_users import User
from src.route66_ext.adapters.db_user_organizations import UserOrganization
from src.route66_ext.db.school_identity import NrruTeacherIdentity
from src.route66_ext.db.school_calendar import SchoolCalendarAttachment
from src.route66_ext.services import school_calendar as calendars
from src.route66_ext.db.academic_classes import AcademicClass, AcademicClassEvent, CourseRegistryBinding, TeachingAssignment
from src.route66_ext.routers.school_identity import context, private, eligible
from src.route66_ext.routers.google_subject_auth import boundary, resources, throttle
from src.route66_ext.services import academic_rosters as roster, learning_access as access
from src.route66_ext.services.nrru_timetable import teacher_timetable
from src.route66_ext.services.nrru_directory import DirectoryUnavailable

router = APIRouter(prefix="/connections")
_REQUEST, _CONNECTED = "class_connection_requested", "class_connection_completed"

class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registry_course_id: str = Field(pattern=r"^[1-9][0-9]{0,19}$")
    academic_year: int = Field(ge=2500, le=2700, strict=True)
    semester: int = Field(ge=1, le=3, strict=True)
    section: str = Field(pattern=r"^[A-Za-z0-9/-]{1,40}$")

class SectionQuery(Section):
    # URL query values arrive as strings; write DTOs remain strict JSON integers.
    academic_year: int = Field(ge=2500, le=2700)
    semester: int = Field(ge=1, le=3)


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: int = Field(gt=0, strict=True)

class AttachCalendar(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision_id: StrictInt = Field(gt=0)


class Setup(Section):
    course_id: int = Field(gt=0, strict=True)


class Connect(Choice):
    confirm_changes: StrictBool
    expected_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")


async def requested(db, request_id, org_id):
    event = await db.get(AcademicClassEvent, request_id)
    if event is None or event.kind != _REQUEST or event.details.get("org_id") != org_id:
        raise HTTPException(404, "Connection request not found")
    return event


async def calendar_attachments(db, event):
    if event is None:
        return []
    rows = (await db.exec(select(SchoolCalendarAttachment).where(
        SchoolCalendarAttachment.request_event_id == event.id).order_by(SchoolCalendarAttachment.id))).all()
    result = []
    for row in rows:
        revision, calendar = await calendars.revision_in_org(db, row.calendar_revision_id,
            event.details['org_id'], editor=True)
        result.append({'revision_id': revision.id, 'name': calendar.name, 'scope': calendar.scope,
                       'attached_at': row.attached_at})
    return result


async def completed(db, event):
    rows = (await db.exec(select(AcademicClassEvent).where(
        AcademicClassEvent.kind == _CONNECTED).order_by(AcademicClassEvent.id.desc()))).all()
    return next((r for r in rows if r.details.get("connection_request_id") == event.id), None)


async def confirmed_teacher(db, user, evidence):
    identity = await db.get(NrruTeacherIdentity, user.id)
    if not eligible(evidence) or identity is None or identity.identity_id != evidence.identity_id:
        raise HTTPException(403, "Confirm your own staff record and sign in with your verified institutional Google account")
    return identity


async def verified_section(db, user, config, evidence, body, request, meetings=False):
    identity = await confirmed_teacher(db, user, evidence)
    async with resources(config) as (redis, _):
        await throttle(redis, request, config, "class-connection-" + str(user.id))
        try:
            timetable = await asyncio.wait_for(teacher_timetable(identity.officer_id, identity.officer_code, body.academic_year, body.semester), timeout=10)
        except (DirectoryUnavailable, TimeoutError, ValueError):
            raise HTTPException(503, "The registrar timetable is unavailable. Retry; no permissions were changed") from None
    exact = [c for c in timetable["classes"] if (c["registry_course_id"], c["section"]) == (body.registry_course_id, body.section)]
    if len(exact) != 1 or (timetable["academic_year"], timetable["semester"]) != (body.academic_year, body.semester):
        raise HTTPException(409, "Select one exact section from your current registrar timetable")
    facts = {**Section.model_validate(body.model_dump(include=set(Section.model_fields))).model_dump(),
             "course_code": exact[0]["course_code"], "title": exact[0]["title"],
             "org_id": config.org_id, "teacher_id": user.id}
    if meetings:
        facts["meetings"] = exact[0]["meetings"]
    return facts


def owned_school_class(cls, org_id, teacher_id):
    """An unmatched school class this exact teacher created in this organization."""
    return cls.course_id is None and cls.org_id == org_id and cls.teacher_user_id == teacher_id


def match_course(db, actor_id, cls, course_id, source):
    # Same stable class/roster/session IDs; the trigger forbids later reassignment.
    cls.course_id = course_id; cls.version += 1; db.add(cls)
    roster.event(db, actor_id, "class_course_matched", {"course_id": course_id, "source": source}, cls)


async def assigned_courses(db, user_id, org_id, registry_course_id):
    return (await db.exec(select(Course).join(CourseRegistryBinding,
        CourseRegistryBinding.course_id == Course.id).join(TeachingAssignment,
        TeachingAssignment.course_id == Course.id).where(Course.org_id == org_id,
        CourseRegistryBinding.registry_course_id == registry_course_id,
        TeachingAssignment.user_id == user_id, TeachingAssignment.active == True))).all()


async def section_classes(db, body):
    # Count every official candidate before considering its native course/permissions.
    return (await db.exec(select(AcademicClass).where(
        AcademicClass.registry_course_id == body.registry_course_id,
        AcademicClass.academic_year == body.academic_year,
        AcademicClass.semester == body.semester, AcademicClass.section == body.section))).all()


async def own_section_request(db, user_id, org_id, body):
    events = (await db.exec(select(AcademicClassEvent).where(
        AcademicClassEvent.kind == _REQUEST, AcademicClassEvent.actor_user_id == user_id)
        .order_by(AcademicClassEvent.id.desc()))).all()
    return next((e for e in events if e.details.get("org_id") == org_id and all(
        e.details.get(k) == getattr(body, k) for k in Section.model_fields)), None)


@router.get("/section")
async def section_status(request: Request, response: Response, body: SectionQuery = Depends(),
                         db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, evidence = await context(request, db)
    courses = await assigned_courses(db, user.id, config.org_id, body.registry_course_id)
    candidates = await section_classes(db, body)
    course_ids = {c.id for c in courses}
    connected = candidates[0] if len(candidates) == 1 and candidates[0].course_id in course_ids else None
    school = candidates[0] if len(candidates) == 1 and owned_school_class(candidates[0], config.org_id, user.id) else None
    event = await own_section_request(db, user.id, config.org_id, body)
    can_request = bool(eligible(evidence) and await db.get(NrruTeacherIdentity, user.id))
    return {"status": "connected" if connected else "conflict" if candidates and not school else
            "ready" if courses else "requested" if event else "needs_course",
            "class_id": connected.id if connected else None,
            "school_class_id": school.id if school else None,
            "request_id": event.id if event else None, "can_request": can_request,
            "calendar_attachments": await calendar_attachments(db, event),
            "courses": [{"id": c.id, "name": c.name} for c in courses]}


@router.get("/official-roster")
async def official_section_roster(request: Request, response: Response,
                                 body: SectionQuery = Depends(),
                                 db: AsyncSession = Depends(get_db_session)):
    """Read the teacher's exact official section without creating a learning class."""
    private(response); user, config, evidence = await context(request, db)
    facts = await verified_section(db, user, config, evidence, body, request)
    cls = SimpleNamespace(**body.model_dump(), registry_course_code=facts["course_code"],
                          registry_class_id=None)
    try:
        rows, _ = await asyncio.wait_for(roster.fetch_roster(cls), timeout=10)
    except (ValueError, TimeoutError):
        raise HTTPException(503, "The official roster is unavailable. Retry from this section") from None
    return {"academic_year": body.academic_year, "semester": body.semester,
            "registry_course_id": body.registry_course_id, "section": body.section,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source_url": roster.source(cls)["url"],
            "students": [{key: row.get(key) for key in
                ("student_number", "full_name_th", "faculty", "program",
                 "registry_status_code", "display_position")} for row in rows]}


@router.post("/setup")
async def setup_section(body: Setup, request: Request, response: Response,
                        db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, evidence = await context(request, db); boundary(request, config)
    facts = await verified_section(db, user, config, evidence, body, request)
    await roster.serialize(db)
    courses = await assigned_courses(db, user.id, config.org_id, body.registry_course_id)
    if body.course_id not in {c.id for c in courses}:
        raise HTTPException(403, "Choose a course already assigned to you and mapped to this official subject")
    binding = await db.get(CourseRegistryBinding, body.course_id)
    if binding.course_code != facts["course_code"]:
        raise HTTPException(409, "The official course code changed. Review its course mapping")
    candidates = await section_classes(db, body)
    school = candidates[0] if len(candidates) == 1 and owned_school_class(candidates[0], config.org_id, user.id) else None
    if len(candidates) > 1 or (candidates and not school and candidates[0].course_id != body.course_id):
        raise HTTPException(409, "This section is already connected elsewhere. Refresh its status")
    if school:
        # Attach the existing school class: roster, schedule and attendance keep their IDs.
        match_course(db, user.id, school, body.course_id, "assigned_teacher")
        await db.flush()
        await access.refresh_course(db, user.id, body.course_id)
        event = await own_section_request(db, user.id, config.org_id, body)
        if event and not await completed(db, event):
            roster.event(db, user.id, _CONNECTED, {"connection_request_id": event.id,
                "course_id": body.course_id, "teacher_id": user.id, "official": facts,
                "setup": "assigned_teacher_school_class"}, school)
        from src.route66_ext.routers.academic_classes import commit
        await commit(db)
        return {"status": "connected", "class_id": school.id, "matched_school_class": True}
    if candidates:
        return {"status": "connected", "class_id": candidates[0].id}
    cls = AcademicClass(org_id=config.org_id, course_id=body.course_id, registry_title=facts["title"],
        registry_course_id=body.registry_course_id,
        registry_course_code=binding.course_code, academic_year=body.academic_year,
        semester=body.semester, section=body.section, registry_class_id=None)
    try:
        rows, digest = await asyncio.wait_for(roster.fetch_roster(cls), timeout=10)
        selected = roster.source(cls)
    except (ValueError, TimeoutError):
        raise HTTPException(503, "The official roster is unavailable. Retry setup") from None
    async with db.begin_nested():
        db.add(cls); await db.flush()
        roster.event(db, user.id, "class_created", {**facts, "course_id": body.course_id,
            "setup": "assigned_teacher"}, cls)
        await roster.apply_roster(db, cls, rows, digest, user.id, selected["kind"], selected["url"])
        event = await own_section_request(db, user.id, config.org_id, body)
        if event and not await completed(db, event):
            roster.event(db, user.id, _CONNECTED, {"connection_request_id": event.id,
                "course_id": body.course_id, "teacher_id": user.id, "official": facts,
                "source_digest": digest, "setup": "assigned_teacher"}, cls)
    from src.route66_ext.routers.academic_classes import commit
    await commit(db)
    return {"status": "connected", "class_id": cls.id, "roster_count": len(rows)}


@router.post("/requests")
async def request_connection(body: Section, request: Request, response: Response,
                             db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, evidence = await context(request, db); boundary(request, config)
    facts = await verified_section(db, user, config, evidence, body, request)
    await roster.serialize(db)
    prior = (await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind == _REQUEST,
        AcademicClassEvent.actor_user_id == user.id).order_by(AcademicClassEvent.id.desc()))).all()
    keys = ("org_id", "registry_course_id", "course_code", "academic_year", "semester", "section")
    found = next((e for e in prior if all(e.details.get(k) == facts[k] for k in keys)), None)
    if found is None:
        found = AcademicClassEvent(actor_user_id=user.id, kind=_REQUEST, details=facts)
        db.add(found); await db.flush()
    done = await completed(db, found)
    await db.commit()
    return {"id": found.id, "status": "connected" if done else "requested",
            "class_id": done.class_id if done else None}


@router.post('/requests/{connection_id}/calendar')
async def attach_calendar(connection_id: int, body: AttachCalendar, request: Request, response: Response,
                          db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, evidence = await context(request, db); boundary(request, config)
    await roster.serialize(db)
    event = await requested(db, connection_id, config.org_id)
    if event.actor_user_id != user.id and user.is_superadmin is not True:
        raise HTTPException(404, 'Connection request not found')
    if user.is_superadmin is not True:
        await confirmed_teacher(db, user, evidence)
    if await completed(db, event):
        raise HTTPException(409, 'This proposal is already connected; its calendar evidence is retained')
    revision, calendar = await calendars.revision_in_org(db, body.revision_id, config.org_id,
        editor=user.is_superadmin is True, user_id=user.id)
    if revision.state != 'published':
        raise HTTPException(409, 'Accept the calendar before attaching it to a proposal')
    if calendar.scope == 'teacher' and calendar.owner_user_id != event.actor_user_id:
        raise HTTPException(404, 'Calendar revision not found')
    if calendar.academic_year != event.details['academic_year']:
        raise HTTPException(409, 'Choose a calendar for this proposal’s academic year')
    exists = (await db.exec(select(SchoolCalendarAttachment).where(
        SchoolCalendarAttachment.request_event_id == event.id,
        SchoolCalendarAttachment.calendar_revision_id == revision.id))).first()
    if exists is None:
        db.add(SchoolCalendarAttachment(request_event_id=event.id, calendar_revision_id=revision.id, attached_by=user.id))
    from src.route66_ext.routers.academic_classes import commit
    await commit(db)
    return {'calendar_attachments': await calendar_attachments(db, event)}


@router.get("/requests")
async def requests(request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, _ = await context(request, db)
    rows = (await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind == _REQUEST)
                         .order_by(AcademicClassEvent.id.desc()))).all()
    result = []
    for row in rows:
        if row.details.get("org_id") != config.org_id or (not user.is_superadmin and row.actor_user_id != user.id): continue
        done = await completed(db, row)
        teacher = await db.get(User, row.actor_user_id)
        result.append({"id": row.id, **row.details, "status": "connected" if done else "requested",
                       "class_id": done.class_id if done else None,
                       "calendar_attachments": await calendar_attachments(db, row),
                       "teacher_name": " ".join([teacher.first_name, teacher.last_name]).strip() if teacher else ""})
    repairs = []
    if user.is_superadmin:
        recent = (await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind.in_(
            ["learning_access_pending", "learning_access_ready"])).order_by(AcademicClassEvent.id.desc()))).all()
        seen = set()
        for row in recent:
            course_id = row.details.get("course_id")
            if type(course_id) is not int or course_id in seen: continue
            seen.add(course_id)
            if row.kind != "learning_access_pending": continue
            course = await db.get(Course, course_id)
            cls = (await db.exec(select(AcademicClass).where(AcademicClass.course_id == course_id)
                                 .order_by(AcademicClass.id).limit(1))).first()
            if course and course.org_id == config.org_id and cls:
                repairs.append({"class_id": cls.id, "course_name": course.name})
    return {"requests": result, "repairs": repairs, "can_connect": user.is_superadmin is True}


async def proposal(db, actor, org_id, event, body):
    d = event.details
    course = await db.get(Course, body.course_id)
    if course is None or course.org_id != org_id: raise HTTPException(404, "Native course not found")
    member = (await db.exec(select(UserOrganization).where(UserOrganization.org_id == org_id,
        UserOrganization.user_id == event.actor_user_id))).one_or_none()
    if member is None: raise HTTPException(409, "The requesting teacher is no longer an organization member")
    binding = await db.get(CourseRegistryBinding, course.id)
    if binding and (binding.registry_course_id, binding.course_code) != (d["registry_course_id"], d["course_code"]):
        raise HTTPException(409, "This native course is mapped to another official course; choose its correct course instead")
    all_candidates = (await db.exec(select(AcademicClass).where(
        AcademicClass.registry_course_id == d["registry_course_id"], AcademicClass.academic_year == d["academic_year"],
        AcademicClass.semester == d["semester"], AcademicClass.section == d["section"]))).all()
    candidate_count = len(all_candidates)
    candidates = [candidate for candidate in all_candidates if candidate.course_id == course.id
                  or owned_school_class(candidate, org_id, event.actor_user_id)]
    if candidate_count > 1 or (all_candidates and not candidates):
        raise HTTPException(409, "An existing class owns this official section. No class or work can be reassigned")
    if len(candidates) > 1:
        raise HTTPException(409, "This official section has ambiguous existing history")
    # A real legacy ID survives from either the existing class or a historical
    # request.  New course-export classes intentionally keep it NULL.
    class_id = candidates[0].registry_class_id if candidates else d.get("registry_class_id")
    if class_id:
        duplicate = (await db.exec(select(AcademicClass).where(AcademicClass.registry_class_id == class_id,
            AcademicClass.academic_year == d["academic_year"], AcademicClass.semester == d["semester"]))).all()
        if duplicate and (len(candidates) != 1 or [r.id for r in duplicate] != [candidates[0].id]):
            raise HTTPException(409, "This official class is already connected elsewhere")
    await access.native.authorize_configuration(db, actor.id, org_id)
    if binding is None and (await db.exec(select(AcademicClass.id).where(AcademicClass.course_id == course.id).limit(1))).first():
        raise HTTPException(409, "This course has unmapped class history; preserve it and review its source before connecting")
    if binding:
        state = await access._configuration_state(db, course.id, org_id, None, True)
    else:
        state = {"binding": None, "group": await access.native.provision_state(db, course.id, org_id),
                 "facts": [], "eligible": [], "delta": {"add_user_ids": [], "remove_members": [], "preserved_manual_count": 0},
                 "enabled": True, "org_id": org_id, "course_id": course.id}
    from src.route66_ext.db.school_identity import SchoolGoogleEvidence
    from src.route66_ext.db.provider_identity import ProviderIdentity
    proof = (await db.exec(select(SchoolGoogleEvidence).join(ProviderIdentity,
        ProviderIdentity.id == SchoolGoogleEvidence.identity_id).where(SchoolGoogleEvidence.user_id == event.actor_user_id,
        ProviderIdentity.user_id == event.actor_user_id, ProviderIdentity.provider == "google",
        ProviderIdentity.retired_at.is_(None)))).one_or_none()
    source_cls = candidates[0] if candidates else SimpleNamespace(
        registry_course_id=d["registry_course_id"], registry_course_code=d["course_code"],
        registry_class_id=class_id, academic_year=d["academic_year"],
        semester=d["semester"], section=d["section"])
    try:
        rows, source_digest = await asyncio.wait_for(roster.fetch_roster(source_cls), timeout=10)
        selected_source = roster.source(source_cls)
    except (ValueError, TimeoutError):
        raise HTTPException(503, "The registrar roster source is unavailable or does not match this exact section. Retry the preview; no IDs or URL are needed.") from None
    digest_policy = "selected_rows_v1" if selected_source["kind"] == "course_rtf" else "legacy_raw_v1"
    attachments = await calendar_attachments(db, event)
    snapshot = {"calendar_attachments": attachments, "teacher_proof": proof.identity_id if proof else None, "actor_id": actor.id, "request_id": event.id, "course_id": course.id,
                "official": d, "registry_class_id": class_id, "state": state,
                "class": candidates[0].model_dump(mode="json") if candidates else None,
                "source": {"kind": selected_source["kind"], "url": selected_source["url"],
                           "digest": source_digest, "digest_policy": digest_policy}}
    fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
    return {"expected_fingerprint": fingerprint, "course_name": course.name, "registry_class_id": class_id,
            "candidate_count": candidate_count, "source_url": selected_source["url"],
            "source_kind": selected_source["kind"], "source_digest": source_digest,
            "source_digest_policy": digest_policy, "roster_count": len(rows),
            "restricts_org_wide_access": state["group"].get("restricts_org_wide_access", False),
            "eligible_count": len(set(state["eligible"]) | ({event.actor_user_id} if proof else set())),
            "calendar_attachments": attachments,
            "native_roles_changed": False, "progress_changed": False}, candidates, rows


@router.post("/requests/{connection_id}/preview")
async def preview_connection(connection_id: int, body: Choice, request: Request, response: Response,
                             db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, _ = await context(request, db); boundary(request, config)
    if user.is_superadmin is not True: raise HTTPException(403, "Administrator course approval required")
    await roster.serialize(db)
    event = await requested(db, connection_id, config.org_id)
    result, _, _ = await proposal(db, user, config.org_id, event, body)
    return result


@router.post("/requests/{connection_id}/connect")
async def connect(connection_id: int, body: Connect, request: Request, response: Response,
                  db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, _ = await context(request, db); boundary(request, config)
    if user.is_superadmin is not True: raise HTTPException(403, "Administrator course approval required")
    if not body.confirm_changes: raise HTTPException(400, "Review the course, teaching assignment and access effect")
    await roster.serialize(db)
    event = await requested(db, connection_id, config.org_id)
    done = await completed(db, event)
    if done:
        if done.details.get("course_id") != body.course_id: raise HTTPException(409, "This request already has another approved course")
        return {"connected": True, "class_id": done.class_id,
                "roster_imported": bool(done.details.get("source_digest")),
                "native_enrollment_changed": False, "progress_changed": False}
    p, candidates, rows = await proposal(db, user, config.org_id, event, body)
    if p["expected_fingerprint"] != body.expected_fingerprint: raise HTTPException(409, "The connection changed. Review it again")
    d = event.details
    async with db.begin_nested():
        binding = await db.get(CourseRegistryBinding, body.course_id)
        if binding is None:
            db.add(CourseRegistryBinding(course_id=body.course_id, registry_course_id=d["registry_course_id"], course_code=d["course_code"]))
        assignment = (await db.exec(select(TeachingAssignment).where(TeachingAssignment.course_id == body.course_id,
            TeachingAssignment.user_id == event.actor_user_id))).one_or_none()
        if assignment is None: assignment = TeachingAssignment(course_id=body.course_id, user_id=event.actor_user_id)
        assignment.active = True; db.add(assignment)
        cls = candidates[0] if candidates else AcademicClass(org_id=config.org_id, course_id=body.course_id,
            registry_title=d.get("title"),
            academic_year=d["academic_year"], semester=d["semester"], section=d["section"],
            registry_course_id=d["registry_course_id"], registry_class_id=p["registry_class_id"], registry_course_code=d["course_code"])
        if cls.id is not None and cls.course_id is None:
            match_course(db, user.id, cls, body.course_id, "administrator_review")
        db.add(cls); await db.flush()
        reviewed = await access.preview(db, user.id, cls, config.org_id)
        await access.apply(db, user.id, cls, config.org_id, expected_fingerprint=reviewed["expected_fingerprint"],
            request_id=body.request_id, reason="Reviewed section connection request " + str(event.id))
        reused_snapshot = bool(cls.last_synced_at and cls.last_source_hash == p["source_digest"]
            and datetime.now(timezone.utc) - cls.last_synced_at < timedelta(minutes=30))
        if not reused_snapshot:
            await roster.apply_roster(db, cls, rows, p["source_digest"], user.id,
                p["source_kind"], p["source_url"])
        roster.event(db, user.id, _CONNECTED, {"connection_request_id": event.id, "course_id": body.course_id,
            "teacher_id": event.actor_user_id, "official": d, "reviewed_fingerprint": body.expected_fingerprint,
            "source_kind": p["source_kind"], "source_url": p["source_url"],
            "source_digest": p["source_digest"], "source_digest_policy": p["source_digest_policy"],
            "reused_recent_snapshot": reused_snapshot}, cls)
        await db.flush()
    from src.route66_ext.routers.academic_classes import commit
    await commit(db)
    return {"connected": True, "class_id": cls.id, "roster_imported": True,
            "native_enrollment_changed": False, "progress_changed": False}
