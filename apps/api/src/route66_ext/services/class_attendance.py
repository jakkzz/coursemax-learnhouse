"""Transactional attendance primitives; caller locks and commits once.

Use the roster's existing global transaction lock before actor/row decisions so
membership imports/revocation and check-in cannot race. Never resolve by email.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import secrets
from uuid import uuid4
from fastapi import HTTPException
from sqlmodel import select
from src.route66_ext.db.class_attendance import AttendanceSession, AttendanceChallenge, AttendanceScan, AttendanceEvent
from src.route66_ext.db.academic_classes import AcademicClass, AcademicRosterEntry, SchoolStudent
from src.route66_ext.services import academic_rosters as roster
from src.route66_ext.services.attendance_policy import SessionPolicy, decide_checkin, token_is_current, CHECKIN_TOKEN_TTL, missing_attendance_status, _utc
from src.route66_ext.services.attendance_handoff import HANDOFF_WINDOW, Reservation


def policy(session):
    return SessionPolicy(session.starts_at, session.ends_at, session.state, session.grace_minutes, session.late_threshold_minutes)


def audit(db, session, actor, kind, details):
    db.add(AttendanceEvent(session_id=session.id, actor_user_id=actor.id, kind=kind, details=details))


async def session_scope(db, session_id, org_id):
    session = await db.get(AttendanceSession, session_id)
    cls = await db.get(AcademicClass, session.class_id) if session else None
    if cls is None:
        raise HTTPException(404, 'Attendance session not found')
    try:
        await roster.class_course(db, cls, org_id)
    except HTTPException:
        raise HTTPException(404, 'Attendance session not found') from None
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


async def decisions_for(db, session_id, entry_id=None):
    rows = (await db.exec(select(AttendanceEvent).where(
        AttendanceEvent.session_id == session_id, AttendanceEvent.kind == 'attendance_decided'
    ).order_by(AttendanceEvent.id))).all()
    return rows if entry_id is None else [row for row in rows if row.details.get('roster_entry_id') == entry_id]


async def collection_started(db, session_id, scans=()):
    if scans:
        return True
    return (await db.exec(select(AttendanceEvent.id).where(
        AttendanceEvent.session_id == session_id, AttendanceEvent.kind == 'checkin_opened').limit(1))).first() is not None


def latest_decision(decisions):
    return max(decisions, key=lambda row: row.id) if decisions else None


def decision_dto(row):
    if row is None:
        return None
    return {'id': row.id, 'status': row.details['status'], 'reason': row.details['reason'],
            'request_id': row.details['request_id'], 'previous_decision_id': row.details.get('previous_decision_id'),
            'actor_user_id': row.actor_user_id, 'decided_at': row.created_at}


def evidence_token(session, class_version, roster_entry_id, scans, decisions):
    latest = latest_decision(decisions)
    evidence = {'session_id': session.id, 'session_version': session.version, 'class_id': session.class_id,
        'class_version': class_version, 'roster_entry_id': roster_entry_id,
        'latest_decision_id': latest.id if latest else None,
        'scans': [(row.id, row.receipt_id, _utc(row.arrived_at).isoformat(), row.kind, row.computed_status)
                  for row in sorted(scans, key=lambda item: item.id)]}
    return sha256(json.dumps(evidence, separators=(',', ':'), sort_keys=True).encode()).hexdigest()


def own_receipt(scan, session, effective_status=None, decision=None):
    return {'receipt_id': scan.receipt_id, 'session_id': session.id, 'class_id': session.class_id,
            'session_title': session.title, 'arrived_at': scan.arrived_at, 'kind': scan.kind,
            'computed_status': scan.computed_status, 'session_state': session.state,
            'effective_status': effective_status or ('no_class' if session.state == 'no_class' else scan.computed_status),
            'decision': decision, 'starts_at': session.starts_at, 'ends_at': session.ends_at, 'timezone': session.timezone}


def scan_projection(session, scans, now, *, decisions=(), collected=False, eligibility='active', class_version=0,
                    roster_entry_id=None):
    earliest = min(scans, key=lambda row: (_utc(row.arrived_at), row.id)) if scans else None
    latest = max(decisions, key=lambda row: row.id) if decisions else None
    decided = decision_dto(latest) if latest else None
    override = latest.details.get('status') if latest else None
    collected = collected or bool(scans)
    if session.state == 'no_class':
        status = 'no_class'
    elif override and override != 'reset':
        status = override
    elif earliest:
        status = earliest.computed_status
    elif eligibility == 'withdrawn':
        status = 'not_eligible'
    elif eligibility != 'active':
        status = 'unknown'
    else:
        status = missing_attendance_status(policy(session), now=now)
        if status == 'absent' and not collected:
            status = 'unrecorded'  # Calendar backfill is not evidence of attendance collection.
    token = evidence_token(session, class_version, roster_entry_id, scans, decisions) if roster_entry_id is not None else None
    return {'status': status, 'effective_status': status, 'evidence_token': token, 'decision': decided,
            'first_arrived_at': earliest.arrived_at if earliest else None,
            'last_heartbeat_at': max((row.arrived_at for row in scans if row.kind == 'heartbeat'), default=None),
            'receipts': [own_receipt(row, session, status, decided) for row in scans]}


def receipt_from_projection(scan, projection):
    return next(row for row in projection['receipts'] if row['receipt_id'] == scan.receipt_id)


async def record_decision(db, session, cls, entry_id, actor, org_id, *, status, reason, expected_token, request_id, now):
    await staff(db, session, cls, actor, org_id)
    entry = await db.get(AcademicRosterEntry, entry_id)
    if entry is None or entry.class_id != cls.id:
        raise HTTPException(404, 'Roster entry not found')
    prior = (await db.exec(select(AttendanceEvent).where(
        AttendanceEvent.session_id == session.id, AttendanceEvent.kind == 'attendance_decided',
        AttendanceEvent.details['request_id'].as_string() == request_id).order_by(AttendanceEvent.id))).all()
    scans = await scans_for(db, session.id, entry.id)
    decisions = await decisions_for(db, session.id, entry.id)
    collected = await collection_started(db, session.id, scans)
    from src.route66_ext.services import attendance_reporting
    student = await db.get(SchoolStudent, entry.student_id)
    timelines = await attendance_reporting.load_membership_timelines(db, cls.id, [(entry, student)])
    eligibility = timelines[entry.id].at(session.starts_at)
    projection = scan_projection(session, scans, now, decisions=decisions, collected=collected,
        eligibility=eligibility, class_version=cls.version, roster_entry_id=entry.id)
    if prior:
        exact = len(prior) == 1 and prior[0].session_id == session.id and prior[0].actor_user_id == actor.id and prior[0].details.get('roster_entry_id') == entry.id and prior[0].details.get('status') == status and prior[0].details.get('reason') == reason and prior[0].details.get('expected_token') == expected_token
        if not exact:
            raise HTTPException(409, {'code': 'request_id_collision', 'message': 'This request ID already belongs to another attendance decision.'})
        return prior[0], projection, True
    if session.state == 'no_class':
        raise HTTPException(409, {'code': 'no_class', 'message': 'Attendance decisions are unavailable while this session is no-class.'})
    if _utc(now) < _utc(session.starts_at):
        raise HTTPException(409, {'code': 'future_session', 'message': 'Future attendance cannot be corrected.'})
    if projection['evidence_token'] != expected_token:
        raise HTTPException(409, {'code': 'stale_evidence', 'message': 'Attendance evidence changed. Reload before reviewing this correction.',
                                  'current_token': projection['evidence_token']})
    previous = latest_decision(decisions)
    row = AttendanceEvent(session_id=session.id, actor_user_id=actor.id, kind='attendance_decided', details={
        'roster_entry_id': entry.id, 'status': status, 'reason': reason, 'expected_token': expected_token,
        'request_id': request_id, 'previous_decision_id': previous.id if previous else None})
    db.add(row)
    await db.flush()
    projection = scan_projection(session, scans, now, decisions=[*decisions, row], collected=collected,
        eligibility=eligibility, class_version=cls.version, roster_entry_id=entry.id)
    return row, projection, False


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


async def challenge_for_token(db, token):
    challenge = (await db.exec(select(AttendanceChallenge).where(AttendanceChallenge.token_hash == sha256(token.encode()).hexdigest()))).first()
    if not challenge:
        raise HTTPException(404, {'code': 'invalid_code'})
    return challenge


async def reserve_scan(db, token, org_id, arrived_at):
    challenge = await challenge_for_token(db, token)
    session, _ = await session_scope(db, challenge.session_id, org_id)
    decision = decide_checkin(policy(session), arrived_at=arrived_at, kind='heartbeat')
    if decision.outcome != 'accepted':
        raise HTTPException(410 if decision.outcome == 'ended' else 409, {'code': decision.outcome})
    if arrived_at >= _utc(session.ends_at):
        raise HTTPException(410, {'code': 'ended'})
    if challenge.session_version != session.version or not token_is_current(expires_at=challenge.expires_at, arrived_at=arrived_at):
        raise HTTPException(410, {'code': 'code_expired'})
    return Reservation(challenge.id, session.id, session.version, arrived_at,
                       min(arrived_at + HANDOFF_WINDOW, _utc(session.ends_at)))


async def accept_scan(db, token, actor, org_id, arrived_at, *, reservation=None):
    challenge = await db.get(AttendanceChallenge, reservation.challenge_id) if reservation else await challenge_for_token(db, token)
    if challenge is None:
        raise HTTPException(410, {'code': 'handoff_expired'})
    session, cls = await session_scope(db, challenge.session_id, org_id)
    entry, _ = await member(db, cls, actor)
    # A retry of an already accepted challenge returns its immutable receipt.
    # Authority is still rechecked above. It does not create new evidence after expiry.
    old = (await db.exec(select(AttendanceScan).where(AttendanceScan.challenge_id == challenge.id, AttendanceScan.roster_entry_id == entry.id))).first()
    existing = await scans_for(db, session.id, entry.id)
    decisions = await decisions_for(db, session.id, entry.id)
    if reservation and (reservation.owner != actor.id or reservation.session_id != session.id):
        raise HTTPException(403, {'code': 'handoff_claimed'})
    if old:
        if old.actor_user_id != actor.id:
            raise HTTPException(403, {'code': 'roster_changed'})
        projection = scan_projection(session, existing, arrived_at, decisions=decisions, collected=True,
            eligibility=entry.status, class_version=cls.version, roster_entry_id=entry.id)
        return receipt_from_projection(old, projection), False
    if reservation:
        if (reservation.session_id != session.id or reservation.session_version != session.version
            or not _utc(challenge.created_at) <= reservation.arrived_at <= arrived_at
            or not arrived_at < reservation.expires_at <= min(reservation.arrived_at + HANDOFF_WINDOW, _utc(session.ends_at))):
            raise HTTPException(410, {'code': 'handoff_expired'})
        observed_at = reservation.arrived_at
    else:
        observed_at = arrived_at
    if challenge.session_version != session.version or not token_is_current(expires_at=challenge.expires_at, arrived_at=observed_at):
        raise HTTPException(410, {'code': 'code_expired'})
    decision = decide_checkin(policy(session), arrived_at=observed_at, kind=challenge.kind, has_record=bool(existing))
    if decision.outcome != 'accepted':
        raise HTTPException(409 if decision.outcome in ('no_class', 'not_open') else 410,
            {'code': decision.outcome, 'message': 'Check-in is closed. Contact your teacher if this is a mistake.'})
    scan = AttendanceScan(receipt_id=str(uuid4()), session_id=session.id, challenge_id=challenge.id,
        roster_entry_id=entry.id, actor_user_id=actor.id, arrived_at=observed_at, kind=challenge.kind, computed_status=decision.computed_status)
    db.add(scan)
    await db.flush()
    audit(db, session, actor, 'checkin_recorded', {'receipt_id': scan.receipt_id, 'roster_entry_id': entry.id, 'kind': scan.kind})
    projection = scan_projection(session, [*existing, scan], arrived_at, decisions=decisions, collected=True,
        eligibility=entry.status, class_version=cls.version, roster_entry_id=entry.id)
    return receipt_from_projection(scan, projection), True

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
