"""Fenced scheduled observations and shared acceptance; no second roster writer."""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import hashlib
import json
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import or_, text
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import select

from src.route66_ext.db.academic_classes import (
    AcademicClass, AcademicClassEvent, AcademicRosterEntry, SchoolStudent,
    CourseRegistryBinding, TeachingAssignment,
)
from src.route66_ext.db.roster_refresh import AcademicRosterRefresh
from src.route66_ext.adapters.db_users import User
from src.route66_ext.adapters.db_user_organizations import UserOrganization
from src.route66_ext.services import academic_rosters as roster

INTERVAL = timedelta(hours=6)
COOLDOWN = timedelta(minutes=30)
LEASE = timedelta(seconds=120)
FACTS = ('org_id', 'course_id', 'teacher_user_id', 'registry_course_id', 'registry_class_id',
         'registry_course_code', 'academic_year', 'semester', 'section')


def utcnow():
    return datetime.now(timezone.utc)


def facts(cls):
    return {key: getattr(cls, key) for key in FACTS}


def semantic_digest(rows):
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


async def state_for(db, cls, *, now=None):
    now = now or utcnow()
    await db.execute(insert(AcademicRosterRefresh).values(class_id=cls.id,
        paused=False, control_version=0, next_check_at=now + INTERVAL, status='ready')
        .on_conflict_do_nothing(index_elements=['class_id']))
    return (await db.exec(select(AcademicRosterRefresh).where(AcademicRosterRefresh.class_id == cls.id)
        .with_for_update().execution_options(populate_existing=True))).one()


async def preview_changes(db, cls, rows):
    current = (await db.exec(select(AcademicRosterEntry, SchoolStudent).join(
        SchoolStudent, SchoolStudent.id == AcademicRosterEntry.student_id)
        .where(AcademicRosterEntry.class_id == cls.id))).all()
    incoming = {row['student_number'] for row in rows}
    existing = {person.student_number: (entry, person) for entry, person in current}
    missing = [(entry, person) for entry, person in current if entry.source == 'registry'
               and entry.status == 'active' and person.student_number not in incoming]
    active = sum(entry.source == 'registry' and entry.status == 'active' for entry, person in current)
    changes = []
    for row in rows:
        prior = existing.get(row['student_number'])
        kind = 'added' if prior is None else 'reactivated' if prior[0].source == 'registry' and prior[0].status == 'withdrawn' else None
        if kind is None and prior and (any(row.get(k) and row[k] != getattr(prior[1], k) for k in ('full_name_th', 'faculty', 'program'))
                                      or row.get('registry_status_code') != prior[0].registry_status_code):
            kind = 'details_updated'
        if kind:
            changes.append({'kind': kind, 'student_number': row['student_number'], 'name': row['full_name_th']})
    changes.extend({'kind': 'withdrawn' if entry.missing_count >= 1 else 'missing_once',
                    'student_number': person.student_number, 'name': person.full_name_th} for entry, person in missing)
    return {'incoming_count': len(rows), 'added_count': len(incoming - set(existing)),
            'missing_count': len(missing), 'withdraw_count': sum(e.missing_count >= 1 for e, p in missing),
            'requires_large_drop_review': active >= 10 and len(rows) < active / 2,
            'active_registry_count': active, 'changes': changes}


async def finish(db, cls, state, actor, outcome, now, details=None, delay=INTERVAL):
    state.status = outcome
    state.last_attempt_at = now
    state.next_check_at = now + delay
    state.lease_id = state.lease_until = None
    event = roster.event(db, actor, 'roster_refresh_finished', {
        'refresh_run_id': actor.run_id if isinstance(actor, roster.ScheduledActor) else uuid4().hex,
        'origin': 'scheduled' if isinstance(actor, roster.ScheduledActor) else 'manual',
        'outcome': outcome, **(details or {})}, cls)
    await db.flush()
    state.result_event_id = event.id
    db.add(state)
    return {'outcome': outcome, 'event_id': event.id, **(details or {})}


async def accept(db, cls, rows, digest, actor, source_kind=None, source_url=None,
                 *, confirm_large_drop=False, now=None):
    """Caller holds the academic lock and owns commit; interactive actor confirms."""
    now = now or utcnow()
    state = await state_for(db, cls, now=now)
    semantic = semantic_digest(rows)
    if not rows or len(rows) > 1000 or len({r['student_number'] for r in rows}) != len(rows):
        raise ValueError('Incomplete or duplicate roster')
    recent = cls.last_synced_at and now - cls.last_synced_at < COOLDOWN
    if recent and (cls.last_source_hash == digest or state.last_semantic_hash == semantic):
        return await finish(db, cls, state, actor, 'recently_applied', now,
                            delay=max(timedelta(), cls.last_synced_at + INTERVAL - now))
    change = await preview_changes(db, cls, rows)
    approved = state.approved_drop
    continuation = bool(approved and approved.get('digest') == semantic
                        and approved.get('version') == cls.version and approved.get('source') == facts(cls))
    human_approval = confirm_large_drop and type(actor) is int
    if change['requires_large_drop_review'] and not (human_approval or continuation):
        return await finish(db, cls, state, actor, 'needs_review', now, {
            'incoming_count': len(rows), 'active_registry_count': change['active_registry_count']})
    counts = await roster.apply_roster(db, cls, rows, digest, actor, source_kind, source_url)
    state.last_semantic_hash = semantic
    result = await finish(db, cls, state, actor, 'applied', now, {
        'counts': counts, 'source_hash': digest, 'source_kind': source_kind,
        'source_url': source_url, 'version': cls.version})
    state.approved_drop = {'digest': semantic, 'version': cls.version, 'source': facts(cls),
                          'actor_user_id': actor, 'event_id': result['event_id']} if human_approval and change['requires_large_drop_review'] else None
    db.add(state)
    return result


async def authorised(db, cls, org_id):
    if cls.last_synced_at is None or cls.last_source_hash is None:
        return False
    try:
        roster.source(cls)
        await roster.class_course(db, cls, org_id)
        if cls.course_id is not None:
            binding = await db.get(CourseRegistryBinding, cls.course_id)
            if not binding or (binding.registry_course_id, binding.course_code) != (cls.registry_course_id, cls.registry_course_code):
                return False
            assigned = (await db.exec(select(TeachingAssignment.id).join(UserOrganization,
                (UserOrganization.user_id == TeachingAssignment.user_id) & (UserOrganization.org_id == org_id))
                .where(TeachingAssignment.course_id == cls.course_id, TeachingAssignment.active == True).limit(1))).first()
            return assigned is not None
        owner = await db.get(User, cls.teacher_user_id) if cls.teacher_user_id else None
        member = (await db.exec(select(UserOrganization.id).where(UserOrganization.user_id == cls.teacher_user_id,
                                                                  UserOrganization.org_id == org_id))).first()
        return bool(owner and member and await roster.verified_owner(db, owner, cls))
    except (HTTPException, ValueError):
        return False


async def initialise(sessions, org_id, now=None):
    """Stagger old accepted classes; no initial roster import or missed-slot replay."""
    now = now or utcnow()
    async with sessions() as db, db.begin():
        rows = (await db.exec(select(AcademicClass).outerjoin(AcademicRosterRefresh,
            AcademicRosterRefresh.class_id == AcademicClass.id).where(AcademicClass.org_id == org_id,
            AcademicClass.last_synced_at.is_not(None), AcademicRosterRefresh.class_id.is_(None)).limit(100))).all()
        for cls in rows:
            due = max(cls.last_synced_at + INTERVAL, now + timedelta(seconds=1 + cls.id * 997 % int(INTERVAL.total_seconds())))
            await db.execute(insert(AcademicRosterRefresh).values(class_id=cls.id,
                paused=False, control_version=0, next_check_at=due, status='ready')
                .on_conflict_do_nothing(index_elements=['class_id']))


@dataclass(frozen=True)
class Claim:
    class_id: int
    token: str
    version: int
    control_version: int
    source: dict


async def claim_one(sessions, org_id, now=None):
    now = now or utcnow()
    async with sessions() as db, db.begin():
        state = (await db.exec(select(AcademicRosterRefresh).join(AcademicClass,
            AcademicClass.id == AcademicRosterRefresh.class_id).where(AcademicClass.org_id == org_id,
            AcademicRosterRefresh.paused == False, AcademicRosterRefresh.next_check_at <= now,
            or_(AcademicRosterRefresh.lease_until.is_(None), AcademicRosterRefresh.lease_until <= now))
            .order_by(AcademicRosterRefresh.next_check_at, AcademicRosterRefresh.class_id)
            .with_for_update(of=AcademicRosterRefresh, skip_locked=True).limit(1))).first()
        if state is None:
            return None
        cls = await db.get(AcademicClass, state.class_id)
        token = uuid4().hex
        if not await authorised(db, cls, org_id):
            await finish(db, cls, state, roster.ScheduledActor(token), 'authority_changed', now)
            return None
        state.lease_id, state.lease_until, state.status = token, now + LEASE, 'checking'
        db.add(state)
        return Claim(cls.id, token, cls.version, state.control_version, facts(cls))


class LeaseExpired(RuntimeError):
    pass


async def complete(sessions, org_id, claim, rows=None, digest=None, *, failure=None, now=None):
    now = now or utcnow()
    async with sessions() as db, db.begin():
        locked = (await db.execute(text('SELECT pg_try_advisory_xact_lock(664466, 1)'))).scalar()
        if not locked:
            # No academic writer lock is acquired while holding this row.
            state = (await db.exec(select(AcademicRosterRefresh).where(AcademicRosterRefresh.class_id == claim.class_id)
                                  .with_for_update(skip_locked=True))).first()
            if state and state.lease_id == claim.token:
                state.lease_id = state.lease_until = None
                state.status, state.next_check_at = 'retrying', now + timedelta(minutes=1)
                db.add(state)
            return {'outcome': 'retrying'}
        state = (await db.exec(select(AcademicRosterRefresh).where(AcademicRosterRefresh.class_id == claim.class_id)
                              .with_for_update())).one()
        if state.lease_id != claim.token or state.lease_until is None or state.lease_until <= now:
            return {'outcome': 'superseded'}
        cls = await db.get(AcademicClass, claim.class_id)
        actor = roster.ScheduledActor(claim.token)
        if state.paused or state.control_version != claim.control_version or cls.version != claim.version or facts(cls) != claim.source:
            return await finish(db, cls, state, actor, 'stale', now, delay=timedelta(minutes=1))
        if not await authorised(db, cls, org_id):
            return await finish(db, cls, state, actor, 'authority_changed', now)
        if failure:
            return await finish(db, cls, state, actor, failure, now)
        selected = roster.source(cls)
        expires = state.lease_until
        result = await accept(db, cls, rows, digest, actor, selected['kind'], selected['url'], now=now)
        if utcnow() >= expires:
            raise LeaseExpired('The writer lease expired; roll back this observation')
        return result


async def run_one(sessions, org_id, claim, fetch=None):
    """Fetching is outside every SQL session; exceptions cannot leak source bodies."""
    try:
        rows, digest = await asyncio.wait_for((fetch or roster.fetch_roster)(SimpleNamespace(**claim.source)), 10)
    except (ValueError, TimeoutError):
        return await complete(sessions, org_id, claim, failure='source_failed')
    try:
        return await asyncio.wait_for(complete(sessions, org_id, claim, rows, digest), 90)
    except asyncio.CancelledError:
        raise
    except Exception:
        # The cancelled/failed writer session has rolled back and closed first.
        return await complete(sessions, org_id, claim, failure='write_failed')
