"""Transactional attendance primitives; caller locks and commits once.

Use the roster's existing global transaction lock before actor/row decisions so
membership imports/revocation and check-in cannot race. Never resolve by email.
"""
from datetime import datetime, timezone
from hashlib import sha256
import secrets
from uuid import uuid4
from fastapi import HTTPException
from sqlmodel import select
from src.route66_ext.db.class_attendance import AttendanceSession, AttendanceChallenge, AttendanceScan, AttendanceEvent
from src.route66_ext.db.academic_classes import AcademicClass, AcademicRosterEntry, SchoolStudent
from src.route66_ext.adapters.db_courses_courses import Course
from src.route66_ext.services import academic_rosters as roster
from src.route66_ext.services.attendance_policy import SessionPolicy, decide_checkin, token_is_current, CHECKIN_TOKEN_TTL, missing_attendance_status


def policy(session):
    return SessionPolicy(session.starts_at, session.ends_at, session.state, session.grace_minutes, session.late_threshold_minutes)


def audit(db, session, actor, kind, details):
    db.add(AttendanceEvent(session_id=session.id, actor_user_id=actor.id, kind=kind, details=details))


async def session_scope(db, session_id, org_id):
    session = await db.get(AttendanceSession, session_id)
    cls = await db.get(AcademicClass, session.class_id) if session else None
    course = await db.get(Course, cls.course_id) if cls else None
    if not course or course.org_id != org_id:
        raise HTTPException(404, 'Attendance session not found')
    return session, cls


async def member(db, cls, actor, *, require_active=True):
    rows = (await db.exec(select(AcademicRosterEntry, SchoolStudent).join(SchoolStudent, SchoolStudent.id == AcademicRosterEntry.student_id).where(
        AcademicRosterEntry.class_id == cls.id, SchoolStudent.user_id == actor.id))).all()
    if len(rows) != 1 or (require_active and rows[0][0].status != 'active'):
        raise HTTPException(403, 'Active class roster membership required')
    entry, student = rows[0]
    if student.student_number:
        owners = (await roster.active_claims(db)).get(student.student_number, {})
        if owners and set(owners) != {actor.id}:
            raise HTTPException(409, 'Student identity needs administrator review; no attendance was changed')
    return entry, student


async def staff(db, session, cls, actor, org_id):
    await roster.can_manage(db, actor, cls, org_id)


async def scans_for(db, session_id, entry_id=None):
    query = select(AttendanceScan).where(AttendanceScan.session_id == session_id)
    if entry_id is not None:
        query = query.where(AttendanceScan.roster_entry_id == entry_id)
    return (await db.exec(query.order_by(AttendanceScan.arrived_at, AttendanceScan.id))).all()


def own_receipt(scan, session):
    return {'receipt_id': scan.receipt_id, 'session_id': session.id, 'class_id': session.class_id,
            'session_title': session.title, 'arrived_at': scan.arrived_at, 'kind': scan.kind,
            'computed_status': scan.computed_status, 'session_state': session.state,
            'starts_at': session.starts_at, 'ends_at': session.ends_at, 'timezone': session.timezone}


def scan_projection(session, scans, now):
    earliest = min(scans, key=lambda s: (s.arrived_at, s.id)) if scans else None
    return {'status': 'no_class' if session.state == 'no_class' else earliest.computed_status if earliest else missing_attendance_status(policy(session), now=now),
            'first_arrived_at': earliest.arrived_at if earliest else None,
            'last_heartbeat_at': max((s.arrived_at for s in scans if s.kind == 'heartbeat'), default=None),
            'receipts': [own_receipt(s, session) for s in scans]}


async def open_challenge(db, session, cls, actor, org_id, kind, now):
    await staff(db, session, cls, actor, org_id)
    decision = decide_checkin(policy(session), arrived_at=now, kind='heartbeat')
    if decision.outcome != 'accepted':
        raise HTTPException(409, {'code': decision.outcome, 'message': 'Check-in is unavailable for this session window or no-class state'})
    raw = secrets.token_urlsafe(32)
    challenge = AttendanceChallenge(session_id=session.id, token_hash=sha256(raw.encode()).hexdigest(),
        session_version=session.version, kind=kind, created_at=now, expires_at=now + CHECKIN_TOKEN_TTL, created_by=actor.id)
    db.add(challenge)
    audit(db, session, actor, 'checkin_opened', {'kind': kind, 'expires_at': challenge.expires_at.isoformat()})
    await db.flush()
    return raw, challenge


async def accept_scan(db, token, actor, org_id, arrived_at):
    challenge = (await db.exec(select(AttendanceChallenge).where(AttendanceChallenge.token_hash == sha256(token.encode()).hexdigest()))).first()
    if not challenge:
        raise HTTPException(404, 'Check-in code not found; ask your teacher for the current code')
    session, cls = await session_scope(db, challenge.session_id, org_id)
    entry, _ = await member(db, cls, actor)
    # A retry of an already accepted challenge returns its immutable receipt.
    # Authority is still rechecked above. It does not create new evidence after expiry.
    old = (await db.exec(select(AttendanceScan).where(AttendanceScan.challenge_id == challenge.id, AttendanceScan.roster_entry_id == entry.id))).first()
    if old:
        return own_receipt(old, session), False
    if challenge.session_version != session.version or not token_is_current(expires_at=challenge.expires_at, arrived_at=arrived_at):
        raise HTTPException(410, 'Check-in code expired or session changed; ask your teacher for a new code')
    existing = await scans_for(db, session.id, entry.id)
    decision = decide_checkin(policy(session), arrived_at=arrived_at, kind=challenge.kind, has_record=bool(existing))
    if decision.outcome != 'accepted':
        raise HTTPException(409 if decision.outcome in ('no_class', 'not_open') else 410,
            {'code': decision.outcome, 'message': 'Check-in is closed. Contact your teacher if this is a mistake.'})
    scan = AttendanceScan(receipt_id=str(uuid4()), session_id=session.id, challenge_id=challenge.id,
        roster_entry_id=entry.id, actor_user_id=actor.id, arrived_at=arrived_at, kind=challenge.kind, computed_status=decision.computed_status)
    db.add(scan)
    await db.flush()
    audit(db, session, actor, 'checkin_recorded', {'receipt_id': scan.receipt_id, 'roster_entry_id': entry.id, 'kind': scan.kind})
    return own_receipt(scan, session), True

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
