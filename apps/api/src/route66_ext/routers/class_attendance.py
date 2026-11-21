"""Native-session attendance and anonymous transient scan reservation; no messaging."""
import asyncio
from contextlib import asynccontextmanager
import json
import time
from datetime import date, datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy import func, text
from redis.exceptions import RedisError
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.route66_ext.adapters.core_events_database import engine, get_db_session
from src.route66_ext.routers.school_identity import context, private
from src.route66_ext.routers.google_subject_auth import settings, boundary, resources, throttle
from src.route66_ext.routers.academic_classes import staff_class, commit
from src.route66_ext.db.class_attendance import AttendanceSession, AttendanceScan, AttendanceEvent
from src.route66_ext.db.academic_classes import AcademicClass, AcademicRosterEntry, SchoolStudent
from src.route66_ext.services import academic_rosters as roster
from src.route66_ext.services import attendance_reporting as reporting
from src.route66_ext.services import class_attendance as service
from src.route66_ext.services.attendance_policy import SessionPolicy, _utc
from src.route66_ext.services.attendance_handoff import Handoffs

router = APIRouter()


class CreateSession(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=160)
    starts_at: datetime
    ends_at: datetime
    timezone: str = Field(default='Asia/Bangkok', max_length=80)
    grace_minutes: StrictInt = Field(default=10, ge=0, le=1440)
    late_threshold_minutes: StrictInt = Field(default=20, ge=0, le=1440)

    @field_validator('title')
    @classmethod
    def title_present(cls, value):
        if not value.strip():
            raise ValueError('Enter a session title')
        return value.strip()

    @field_validator('starts_at', 'ends_at')
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Session times require an explicit UTC offset')
        return value.astimezone(timezone.utc)

    @field_validator('timezone')
    @classmethod
    def known_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Choose a valid IANA timezone') from None
        return value

    @model_validator(mode='after')
    def valid_policy(self):
        SessionPolicy(self.starts_at, self.ends_at, grace_minutes=self.grace_minutes, late_threshold_minutes=self.late_threshold_minutes)
        return self


class ChangeState(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: StrictInt = Field(ge=0)
    state: str = Field(pattern=r'^(scheduled|no_class)$')
    reason: str = Field(min_length=5, max_length=500)

    @field_validator('reason')
    @classmethod
    def reason_present(cls, value):
        if len(value.strip()) < 5:
            raise ValueError('Enter a meaningful reason')
        return value.strip()


class OpenChallenge(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: str = Field(default='entry', pattern=r'^(entry|heartbeat)$')


class ScanCode(BaseModel):
    model_config = ConfigDict(extra='forbid')
    token: str = Field(pattern=r'^[A-Za-z0-9_-]{43}$')


class CompleteScan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    handoff: str = Field(pattern=r'^[A-Za-z0-9_-]{43}$')


class AttendanceDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    roster_entry_id: StrictInt = Field(gt=0)
    status: str = Field(pattern=r'^(present|late|absent|excused|reset)$')
    reason: str = Field(min_length=5, max_length=500)
    expected_token: str = Field(pattern=r'^[0-9a-f]{64}$')
    request_id: UUID

    @field_validator('reason')
    @classmethod
    def decision_reason(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError('Enter a meaningful reason')
        return value


def session_dto(row):
    return {k: getattr(row, k) for k in ('id', 'class_id', 'title', 'starts_at', 'ends_at', 'timezone', 'grace_minutes', 'late_threshold_minutes', 'state', 'version',
                                         'calendar_kind', 'academic_week', 'slot_key', 'nominal_on', 'replaces_session_id', 'mode', 'location', 'note')}


@asynccontextmanager
async def report_read_snapshot():
    async with AsyncSession(engine, expire_on_commit=False) as db:
        async with db.begin():
            await db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            as_of = (await db.execute(text('SELECT statement_timestamp()'))).scalar_one()
            yield db, as_of


def report_value(callable_):
    try:
        return callable_()
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


@router.get('/classes/{class_id}/sessions')
async def sessions(class_id: int, request: Request, response: Response, session: int | None = None,
                   db: AsyncSession = Depends(get_db_session)):
    private(response)
    actor, config, _ = await context(request, db)
    cls = await db.get(AcademicClass, class_id)
    if cls is None:
        raise HTTPException(404, 'Class not found')
    course = await roster.class_course(db, cls, config.org_id)
    manageable = True
    try:
        await roster.can_manage(db, actor, cls, config.org_id)
    except HTTPException as error:
        if error.status_code != 403:
            raise
        manageable = False
        await service.member(db, cls, actor, require_active=False)
    rows = (await db.exec(select(AttendanceSession).where(AttendanceSession.class_id == class_id).order_by(AttendanceSession.starts_at.desc()).limit(200))).all()
    if session is not None and session not in {r.id for r in rows}:
        # A linked session beyond the recent page stays reachable under the same class authority.
        selected = await db.get(AttendanceSession, session)
        if selected is None or selected.class_id != class_id:
            raise HTTPException(404, 'Attendance session not found')
        rows = [*rows, selected]
    return {'class_id': cls.id, 'course_name': course.name if course else cls.registry_title or cls.registry_course_code, 'section': cls.section, 'manageable': manageable, 'sessions': [session_dto(r) for r in rows]}


@router.get('/classes/{class_id}/summary')
async def attendance_summary(class_id: int, request: Request, response: Response,
                             from_date: date | None = Query(default=None, alias='from'),
                             to_date: date | None = Query(default=None, alias='to')):
    private(response)
    async with report_read_snapshot() as (db, as_of):
        actor, config, _ = await context(request, db)
        cls = await db.get(AcademicClass, class_id)
        if cls is None:
            raise HTTPException(404, 'Class not found')
        await roster.can_manage(db, actor, cls, config.org_id)
        data = await reporting.load_class_data(db, cls)
        return report_value(lambda: reporting.class_summary(data, as_of, from_date, to_date))


@router.get('/classes/{class_id}/history')
async def attendance_history(class_id: int, request: Request, response: Response,
                             roster_entry_id: int = Query(gt=0), before: str | None = Query(default=None, max_length=300)):
    private(response)
    async with report_read_snapshot() as (db, as_of):
        actor, config, _ = await context(request, db)
        cls = await db.get(AcademicClass, class_id)
        if cls is None:
            raise HTTPException(404, 'Class not found')
        await roster.can_manage(db, actor, cls, config.org_id)
        data = await reporting.load_class_data(db, cls)
        member_row = next(((entry, student) for entry, student in data.entries if entry.id == roster_entry_id), None)
        if member_row is None:
            raise HTTPException(404, 'Roster entry not found')
        return report_value(lambda: reporting.manager_history(data, *member_row, as_of, before))


@router.get('/classes/{class_id}/own')
async def own_attendance(class_id: int, request: Request, response: Response,
                         from_date: date | None = Query(default=None, alias='from'),
                         to_date: date | None = Query(default=None, alias='to'),
                         before: str | None = Query(default=None, max_length=300)):
    private(response)
    async with report_read_snapshot() as (db, as_of):
        actor, config, _ = await context(request, db)
        cls = await db.get(AcademicClass, class_id)
        if cls is None:
            raise HTTPException(404, 'Class not found')
        await roster.class_course(db, cls, config.org_id)
        entry, student = await service.member(db, cls, actor, require_active=False)
        data = await reporting.load_class_data(db, cls)
        return report_value(lambda: reporting.own_report(
            data, entry, student, as_of, from_date, to_date, before))


@router.get('/classes/{class_id}/summary.csv')
async def attendance_summary_csv(class_id: int, request: Request,
                                 from_date: date | None = Query(default=None, alias='from'),
                                 to_date: date | None = Query(default=None, alias='to')):
    async with report_read_snapshot() as (db, as_of):
        actor, config, _ = await context(request, db)
        cls = await db.get(AcademicClass, class_id)
        if cls is None:
            raise HTTPException(404, 'Class not found')
        await roster.can_manage(db, actor, cls, config.org_id)
        data = await reporting.load_class_data(db, cls)
        report = report_value(lambda: reporting.class_summary(data, as_of, from_date, to_date))
        content = reporting.summary_csv(report)
    return Response(content=content, media_type='text/csv', headers={
        'Cache-Control': 'private, no-store', 'Vary': 'Cookie, Authorization',
        'Content-Disposition': 'attachment; filename="attendance-summary.csv"'})


@router.post('/classes/{class_id}/sessions')
async def create(class_id: int, body: CreateSession, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    actor, config, _ = await context(request, db)
    boundary(request, config)
    await roster.serialize(db)
    cls = await staff_class(db, actor, config.org_id, class_id)
    row = AttendanceSession(class_id=cls.id, created_by=actor.id, **body.model_dump())
    db.add(row)
    await db.flush()
    service.audit(db, row, actor, 'session_created', {**session_dto(row), 'starts_at': row.starts_at.isoformat(), 'ends_at': row.ends_at.isoformat()})
    # Freeze class setup once it owns attendance, even before a roster is imported.
    cls.version += 1
    db.add(cls)
    await commit(db)
    return session_dto(row)


@router.get('/sessions/{session_id}')
async def detail(session_id: int, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    return await session_snapshot(request, db, session_id)


async def attendance_head(db, session_id):
    event = select(func.max(AttendanceEvent.id)).where(AttendanceEvent.session_id == session_id).scalar_subquery()
    head = (await db.exec(select(AttendanceSession.version, AcademicClass.version, event).join(
        AcademicClass, AcademicClass.id == AttendanceSession.class_id).where(AttendanceSession.id == session_id))).first()
    if head is None:
        raise HTTPException(404, 'Attendance session not found')
    return ':'.join(str(value or 0) for value in head)


async def session_snapshot(request, db, session_id):
    actor, config, _ = await context(request, db)
    # Read the cursor before the projection so a concurrent commit is not skipped.
    cursor = await attendance_head(db, session_id)
    row, cls = await service.session_scope(db, session_id, config.org_id)
    manageable = True
    try:
        await roster.can_manage(db, actor, cls, config.org_id)
    except HTTPException as error:
        if error.status_code != 403:
            raise
        manageable = False
    now = datetime.now(timezone.utc)
    entries = (await db.exec(select(AcademicRosterEntry, SchoolStudent).join(
        SchoolStudent, SchoolStudent.id == AcademicRosterEntry.student_id
    ).where(AcademicRosterEntry.class_id == cls.id).order_by(AcademicRosterEntry.display_position))).all()
    scans = await service.scans_for(db, row.id)
    decisions = await service.decisions_for(db, row.id)
    collected = await service.collection_started(db, row.id, scans)
    timelines = await reporting.load_membership_timelines(db, cls.id, list(entries))
    scans_by_entry = {}
    for scan in scans:
        scans_by_entry.setdefault(scan.roster_entry_id, []).append(scan)
    decisions_by_entry = {}
    for event in decisions:
        decisions_by_entry.setdefault(event.details.get('roster_entry_id'), []).append(event)
    if not manageable:
        entry, _ = await service.member(db, cls, actor, require_active=False)
        own = service.scan_projection(row, scans_by_entry.get(entry.id, []), now,
            decisions=decisions_by_entry.get(entry.id, []), collected=collected,
            eligibility=timelines[entry.id].at(row.starts_at), class_version=cls.version, roster_entry_id=entry.id)
        return {'session': session_dto(row), 'manageable': False, 'own': own, 'cursor': cursor, 'as_of': now}
    events = (await db.exec(select(AttendanceEvent).where(
        AttendanceEvent.session_id == row.id).order_by(AttendanceEvent.id.desc()).limit(30))).all()
    return {'session': session_dto(row), 'manageable': True, 'cursor': cursor, 'as_of': now, 'students': [
        {'roster_entry_id': entry.id, 'name': student.full_name_th, 'student_number': student.student_number,
         'membership': entry.status, **service.scan_projection(row, scans_by_entry.get(entry.id, []), now,
             decisions=decisions_by_entry.get(entry.id, []), collected=collected,
             eligibility=timelines[entry.id].at(row.starts_at), class_version=cls.version, roster_entry_id=entry.id)}
        for entry, student in entries],
        'events': [{'id': event.id, 'kind': event.kind, 'created_at': event.created_at, 'details': event.details} for event in events]}


def clock_phase(snapshot, now=None):
    now = now or datetime.now(timezone.utc)
    row = snapshot['session']
    return (now >= _utc(row['starts_at']), now >= _utc(row['ends_at']))


async def session_events(request, session_id, first, *, interval=1, lifetime=55):
    snapshot = first
    head, phase = snapshot['cursor'], clock_phase(snapshot, snapshot['as_of'])
    checked, started = time.monotonic(), time.monotonic()
    yield 'id: ' + head + '\ndata: ' + json.dumps(jsonable_encoder(snapshot), separators=(',', ':')) + '\n\n'
    while time.monotonic() - started < lifetime:
        await asyncio.sleep(interval)
        if await request.is_disconnected():
            return
        try:
            async with AsyncSession(engine, expire_on_commit=False) as db:
                current = await attendance_head(db, session_id)
                changed = current != head or clock_phase(snapshot) != phase
                if not changed and time.monotonic() - checked < 10:
                    continue
                # Recheck native session, MFA, staff authority and roster before any payload.
                snapshot = await session_snapshot(request, db, session_id)
            # The connection is released BEFORE yielding or waiting for another event.
            head, phase, checked = snapshot['cursor'], clock_phase(snapshot, snapshot['as_of']), time.monotonic()
            yield 'id: ' + head + '\ndata: ' + json.dumps(jsonable_encoder(snapshot), separators=(',', ':')) + '\n\n'
        except HTTPException as error:
            yield 'event: access_lost\ndata: ' + json.dumps({'status': error.status_code}) + '\n\n'
            return


@router.get('/sessions/{session_id}/events')
async def events(session_id: int, request: Request):
    async with AsyncSession(engine, expire_on_commit=False) as db:
        first = await session_snapshot(request, db, session_id)
    return StreamingResponse(session_events(request, session_id, first), media_type='text/event-stream',
        headers={'Cache-Control': 'private, no-store', 'Vary': 'Cookie, Authorization', 'X-Accel-Buffering': 'no'})


@router.post('/sessions/{session_id}/state')
async def change_state(session_id: int, body: ChangeState, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    actor, config, _ = await context(request, db)
    boundary(request, config)
    await roster.serialize(db)
    row, cls = await service.session_scope(db, session_id, config.org_id)
    await service.staff(db, row, cls, actor, config.org_id)
    if row.version != body.expected_version or row.state == body.state:
        raise HTTPException(409, 'Session changed or already has this state. Reload before reviewing again.')
    before = row.state
    row.state = body.state
    row.version += 1
    db.add(row)
    service.audit(db, row, actor, 'session_state_changed', {'from': before, 'to': row.state, 'reason': body.reason, 'version': row.version})
    await commit(db)
    return session_dto(row)


@router.post('/sessions/{session_id}/decisions')
async def decide(session_id: int, body: AttendanceDecision, request: Request, response: Response,
                 db: AsyncSession = Depends(get_db_session)):
    private(response)
    now = datetime.now(timezone.utc)
    actor, config, _ = await context(request, db)
    boundary(request, config)
    await roster.serialize(db)
    row, cls = await service.session_scope(db, session_id, config.org_id)
    decision, projection, retried = await service.record_decision(db, row, cls, body.roster_entry_id,
        actor, config.org_id, status=body.status, reason=body.reason,
        expected_token=body.expected_token, request_id=str(body.request_id), now=now)
    await commit(db)
    return {'decision': service.decision_dto(decision), 'projection': projection, 'retried': retried}


@router.post('/sessions/{session_id}/open')
async def open_checkin(session_id: int, body: OpenChallenge, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    now = datetime.now(timezone.utc)
    actor, config, _ = await context(request, db)
    boundary(request, config)
    async with resources(config) as (redis, _):
        await throttle(redis, request, config, 'attendance-open-' + str(actor.id))
    await roster.serialize(db)
    row, cls = await service.session_scope(db, session_id, config.org_id)
    token, challenge = await service.open_challenge(db, row, cls, actor, config.org_id, body.kind, now)
    await commit(db)
    # Fragment is never sent in HTTP URLs/access logs. The page submits via POST.
    return {'token': token, 'checkin_url': config.handoff.client.public_origin + '/attendance/check-in#' + token,
            'kind': challenge.kind, 'expires_at': challenge.expires_at, 'session_id': row.id, 'session_version': row.version,
            'server_now': datetime.now(timezone.utc)}


@router.post('/check-in')
async def checkin(body: ScanCode, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    arrived_at = datetime.now(timezone.utc)
    actor, config, _ = await context(request, db)
    boundary(request, config)
    async with resources(config) as (redis, _):
        await throttle(redis, request, config, 'attendance-scan-' + str(actor.id))
    await roster.serialize(db)
    receipt, created = await service.accept_scan(db, body.token, actor, config.org_id, arrived_at)
    await commit(db)
    return {'receipt': receipt, 'created': created}


@router.post('/check-in/prepare')
async def prepare(body: ScanCode, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    arrived_at = datetime.now(timezone.utc)
    config = settings()
    boundary(request, config)
    try:
        async with resources(config) as (redis, _):
            # A classroom shares an IP; the ordinary login budget is not its size limit.
            await throttle(redis, request, config, 'attendance-prepare', limit=600)
            reservation = await service.reserve_scan(db, body.token, config.org_id, arrived_at)
            handle = await Handoffs(redis, config.deployment).create(reservation)
    except (RedisError, RuntimeError):
        raise HTTPException(503, {'code': 'handoff_unavailable'}) from None
    return {'handoff': handle, 'expires_at': reservation.expires_at,
            'return_path': '/attendance/check-in?handoff=' + handle}


@router.post('/check-in/complete')
async def complete(body: CompleteScan, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    now = datetime.now(timezone.utc)
    config = settings()
    boundary(request, config)
    actor, config, _ = await context(request, db)
    await roster.serialize(db)
    try:
        async with resources(config) as (redis, _):
            await throttle(redis, request, config, 'attendance-scan-' + str(actor.id))
            store = Handoffs(redis, config.deployment)
            pending = await store.get(body.handoff)
            _, cls = await service.session_scope(db, pending.session_id, config.org_id)
            # An unrelated account must not take ownership just by trying the link.
            await service.member(db, cls, actor)
            if pending.owner and pending.owner != actor.id:
                raise HTTPException(409, {'code': 'handoff_claimed'})
            reservation = await store.claim(body.handoff, actor.id)
        receipt, created = await service.accept_scan(db, None, actor, config.org_id, now, reservation=reservation)
        await commit(db)
    except ValueError:
        raise HTTPException(410, {'code': 'handoff_expired'}) from None
    except RedisError:
        raise HTTPException(503, {'code': 'handoff_unavailable'}) from None
    return {'receipt': receipt, 'created': created}


@router.get('/receipts/{receipt_id}')
async def receipt(receipt_id: str, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    actor, config, _ = await context(request, db)
    scan = (await db.exec(select(AttendanceScan).where(
        AttendanceScan.receipt_id == receipt_id, AttendanceScan.actor_user_id == actor.id))).first()
    if not scan:
        raise HTTPException(404, 'Receipt not found')
    row, cls = await service.session_scope(db, scan.session_id, config.org_id)
    entry, _ = await service.member(db, cls, actor, require_active=False)
    if entry.id != scan.roster_entry_id:
        raise HTTPException(404, 'Receipt not found')
    scans = await service.scans_for(db, row.id, entry.id)
    decisions = await service.decisions_for(db, row.id, entry.id)
    own = service.scan_projection(row, scans, datetime.now(timezone.utc), decisions=decisions,
        collected=True, eligibility=entry.status, class_version=cls.version, roster_entry_id=entry.id)
    return service.receipt_from_projection(scan, own)

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
