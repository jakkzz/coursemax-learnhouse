"""Identity review over the existing append-only academic journal.

A review can retry the existing exact-match writer or close a report unchanged.
It cannot transfer identities, merge school records or move academic evidence.
Callers serialize writes using academic_rosters.serialize and own the transaction.
"""
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlmodel import select

from src.route66_ext.adapters.db_courses_courses import Course
from src.route66_ext.adapters.db_user_organizations import UserOrganization
from src.route66_ext.adapters.db_users import User
from src.route66_ext.db.academic_classes import AcademicClass, AcademicClassEvent, AcademicRosterEntry, SchoolStudent
from src.route66_ext.services import academic_rosters as roster
from src.route66_ext.services.nrru_directory import student_hint

REQUEST = 'identity_review_requested'
DECISION = 'identity_review_decided'


def scoped(org_id):
    return select(AcademicClassEvent).outerjoin(AcademicClass, AcademicClass.id == AcademicClassEvent.class_id).where(
        AcademicClassEvent.kind == REQUEST,
        or_(AcademicClass.org_id == org_id, and_(AcademicClassEvent.class_id.is_(None),
            AcademicClassEvent.details['org_id'].as_string() == str(org_id))))


async def get_case(db, case_id, org_id):
    case = (await db.exec(scoped(org_id).where(AcademicClassEvent.id == case_id))).first()
    if case is None:
        raise HTTPException(404, 'Review request not found')
    return case


async def decision(db, case):
    return (await db.exec(select(AcademicClassEvent).where(
        AcademicClassEvent.kind == DECISION,
        AcademicClassEvent.details['case_id'].as_string() == str(case.id))
        .order_by(AcademicClassEvent.id.desc()).limit(1))).first()


async def request_review(db, actor_id, org_id, student, reason, cls=None, entry_id=None):
    query = scoped(org_id).where(AcademicClassEvent.student_id == student.id)
    if cls is not None:
        query = query.where(AcademicClassEvent.class_id == cls.id)
    else:
        query = query.where(AcademicClassEvent.class_id.is_(None), AcademicClassEvent.actor_user_id == actor_id)
    for previous in (await db.exec(query.order_by(AcademicClassEvent.id.desc()))).all():
        if await decision(db, previous) is None:
            if previous.details['reason'] != reason:
                raise HTTPException(409, 'An identity review is already open. View the existing request; its original reason was kept.')
            return previous
    details = {'org_id': org_id, 'reason': reason}
    if cls is None:
        details['subject_user_id'] = actor_id
    if entry_id is not None:
        details['entry_id'] = entry_id
    case = roster.event(db, actor_id, REQUEST, details, cls, student)
    await db.flush()
    return case


async def own_profile(db, user_id, org_id, evidence):
    number = student_hint(evidence.email, evidence.hosted_domain) if evidence else None
    profile = (await db.exec(select(SchoolStudent).where(
        SchoolStudent.student_number == number if number else SchoolStudent.user_id == user_id))).first()
    if profile is None:
        return None
    member = (await db.exec(select(AcademicRosterEntry.id).join(AcademicClass, AcademicClass.id == AcademicRosterEntry.class_id).where(
        AcademicRosterEntry.student_id == profile.id, AcademicClass.org_id == org_id).limit(1))).first()
    return profile if member is not None else None


async def evidence_for(db, case, org_id):
    profile = await db.get(SchoolStudent, case.student_id)
    claims = (await roster.active_claims(db)).get(profile.student_number, {}) if profile else {}
    claimant = next(iter(claims)) if len(claims) == 1 else None
    other = (await db.exec(select(SchoolStudent).where(SchoolStudent.user_id == claimant))).first() if claimant else None
    member = (await db.exec(select(UserOrganization).where(UserOrganization.user_id == claimant,
        UserOrganization.org_id == org_id))).first() if claimant else None
    if profile is None:
        state = 'record_missing'
    elif not profile.student_number or not profile.has_registry_evidence:
        state = 'waiting_for_roster'
    elif not claims:
        state = 'google_signin_needed'
    elif len(claims) != 1:
        state = 'multiple_claims'
    elif (profile.user_id is not None and profile.user_id != claimant) or (other and other.id != profile.id):
        state = 'ownership_conflict'
    elif case.details.get('subject_user_id', claimant) != claimant:
        state = 'original_account_needed'
    elif member is None:
        state = 'organization_access_needed'
    else:
        state = 'matched' if profile.user_id == claimant else 'ready_to_match'
    closed = await decision(db, case)
    facts = {'case_id': case.id, 'decision_id': closed.id if closed else None, 'state': state,
        'profile': {k: getattr(profile, k) for k in ('id', 'student_number', 'has_registry_evidence', 'user_id', 'identity_id', 'full_name_th', 'faculty', 'program')} if profile else None,
        'claims': sorted(claims.items()), 'other_profile': other.id if other else None}
    token = hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return profile, claims, state, closed, token


async def view(db, case, org_id, *, reviewer=False, manager=False):
    profile, claims, state, closed, token = await evidence_for(db, case, org_id)
    result = {'id': case.id, 'created_at': case.created_at, 'status': 'closed' if closed else 'open',
        'outcome': closed.details['outcome'] if closed else None, 'decided_at': closed.created_at if closed else None,
        'reason': case.details['reason'], 'student_number': profile.student_number if profile else None,
        'match_state': state}
    if reviewer or manager:
        cls = await db.get(AcademicClass, case.class_id) if case.class_id else None
        course = await db.get(Course, cls.course_id) if cls and cls.course_id else None
        result.update({'student_name': profile.full_name_th if profile else None,
            'class_name': (course.name if course else cls.registry_title or cls.registry_course_code) if cls else None,
            'section': cls.section if cls else None})
    if reviewer:
        # Private Google emails/subjects and out-of-organization account details stay out of DTOs.
        accounts = (await db.exec(select(User).join(UserOrganization, UserOrganization.user_id == User.id).where(
            UserOrganization.org_id == org_id, User.id.in_(set(claims) | ({profile.user_id} if profile and profile.user_id else set()))))).all()
        result.update({'expected_token': token, 'can_match': not closed and state in ('ready_to_match', 'matched'),
            'accounts': [{'name': ' '.join([u.first_name, u.last_name]).strip() or u.username,
                'owns_record': bool(profile and profile.user_id == u.id), 'has_verified_claim': u.id in claims} for u in accounts],
            'decision_reason': closed.details['reason'] if closed else None})
    return result


async def decide(db, actor_id, org_id, case, action, reason, expected_token):
    profile, claims, state, closed, token = await evidence_for(db, case, org_id)
    if closed or token != expected_token:
        raise HTTPException(409, 'The review or verified evidence changed. Reload before deciding.')
    cls = await db.get(AcademicClass, case.class_id) if case.class_id else None
    evidence = {'match_state': state, 'owner_user_id': profile.user_id if profile else None,
        'verified_claims': [{'user_id': uid, 'identity_id': identity} for uid, identity in sorted(claims.items())]}
    if action == 'recheck':
        if state not in ('ready_to_match', 'matched'):
            raise HTTPException(409, 'Current evidence does not permit an exact match. Reload to see the next action.')
        result = await roster.reconcile(db, actor_id, profile.student_number, {profile.student_number: claims}, cls)
        if result != 'matched':
            raise HTTPException(409, 'Identity cannot be matched without changing existing ownership.')
        await db.flush()
        # Reuse the existing optional native-access repair; no second enrollment writer.
        from src.route66_ext.services.learning_access import refresh_course
        courses = (await db.exec(select(AcademicClass.course_id).join(AcademicRosterEntry,
            AcademicRosterEntry.class_id == AcademicClass.id).where(AcademicRosterEntry.student_id == profile.id,
            AcademicClass.org_id == org_id, AcademicClass.course_id.is_not(None)).distinct())).all()
        for course_id in sorted(courses):
            await refresh_course(db, actor_id, course_id)
        outcome = 'matched'
    elif action == 'close':
        outcome = 'unchanged'
    else:
        raise HTTPException(422, 'Choose a supported review decision')
    # Keep private decision evidence out of the teacher's raw class-event feed.
    # Teacher/student receipts are projected through the scoped review endpoints.
    roster.event(db, actor_id, DECISION, {'case_id': case.id, 'org_id': org_id,
        'outcome': outcome, 'reason': reason, 'evidence_token': token, 'evidence': evidence}, student=profile)
    await db.flush()
    return await view(db, case, org_id, reviewer=True)
