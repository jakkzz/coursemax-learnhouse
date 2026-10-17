"""Shared calendar revisions and reviewed class schedules over one session authority.

Callers hold the roster transaction lock for writes and commit once. Calendar
meetings are ordinary AttendanceSession rows: preview never writes, apply only
inserts or changes state through the audited path, and past or evidence-bearing
sessions are never changed automatically.
"""
from datetime import datetime, timezone
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func
from sqlmodel import select
from src.route66_ext.db.academic_classes import AcademicClass
from src.route66_ext.db.class_attendance import AttendanceSession, AttendanceChallenge, AttendanceEvent
from src.route66_ext.db.school_calendar import SchoolCalendar, SchoolCalendarSource, SchoolCalendarRevision, ClassSchedule
from src.route66_ext.services import academic_rosters as roster
from src.route66_ext.services import calendar_plan as planner

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 200_000
_COMPARED = ('starts_at', 'ends_at', 'timezone', 'state', 'title', 'rotation', 'mode', 'location', 'note', 'nominal_on')


def payload_model(data):
    try:
        return planner.Payload.model_validate(data)
    except ValidationError as error:
        raise HTTPException(422, {'code': 'invalid_calendar', 'errors': [
            {'loc': list(e['loc']), 'msg': e['msg']} for e in error.errors()]}) from None


def can_edit(calendar, user):
    return bool(user and (user.is_superadmin is True or
                (calendar.scope == 'teacher' and calendar.owner_user_id == user.id)))


async def calendar_summary(db, calendar, user=None):
    rows = (await db.exec(select(SchoolCalendarRevision.id, SchoolCalendarRevision.state).where(
        SchoolCalendarRevision.calendar_id == calendar.id))).all()
    published = max((i for i, state in rows if state == 'published'), default=None)
    payload = await db.get(SchoolCalendarRevision, published) if published else None
    return {'id': calendar.id, 'name': calendar.name, 'academic_year': calendar.academic_year,
            'track': calendar.track, 'scope': calendar.scope, 'can_edit': can_edit(calendar, user),
            'published_revision_id': published,
            'has_teaching_weeks': bool(payload and planner.has_teaching_weeks(planner.Payload.model_validate(payload.payload))),
            'latest_revision_id': max((i for i, _ in rows), default=None)}


async def revision_dto(db, revision, include_pages=True, user=None):
    calendar = await db.get(SchoolCalendar, revision.calendar_id)
    source = await db.get(SchoolCalendarSource, revision.source_id) if revision.source_id else None
    payload = planner.Payload.model_validate(revision.payload)
    return {'id': revision.id, 'calendar_id': revision.calendar_id, 'number': revision.number,
            'version': revision.version, 'state': revision.state, 'payload': revision.payload,
            'source_id': source.id if source else None, 'source_name': source.filename if source else None,
            'source_hash': source.sha256 if source else None, 'source_page_count': source.page_count if source else None,
            'source_truncated': source.truncated if source else False,
            'source_pages': source.pages if source and include_pages else [],
            **_source_kind(source),
            'parse_note': revision.parse_note, 'issues': planner.issues(payload, source.page_count if source else None),
            **provenance(revision), 'derived_from_revision_id': revision.derived_from_revision_id,
            'published_at': revision.published_at, 'calendar': await calendar_summary(db, calendar, user)}


def _source_kind(source):
    from src.route66_ext.services import nrru_calendar_pdf
    combined = nrru_calendar_pdf.abridged(source.pages or []) if source else None
    return {'source_kind': combined['kind'] if combined else None,
            'source_programs': combined['programs'] if combined else []}


async def revision_in_org(db, revision_id, org_id, *, editor=False, user_id=None):
    revision = await db.get(SchoolCalendarRevision, revision_id)
    calendar = await db.get(SchoolCalendar, revision.calendar_id) if revision else None
    owner = calendar and calendar.scope == 'teacher' and calendar.owner_user_id == user_id
    if (calendar is None or calendar.org_id != org_id
        or (calendar.scope == 'teacher' and not (owner or editor))
        or (revision.state != 'published' and not (owner or editor))):
        raise HTTPException(404, 'Calendar revision not found')
    return revision, calendar


def provenance(revision):
    return {key: getattr(revision, key) for key in ('source_url', 'resolved_url', 'fetched_at')}


async def copy_source(db, source_id, calendar_id):
    if source_id is None:
        return None
    original = await db.get(SchoolCalendarSource, source_id)
    copy = (await db.exec(select(SchoolCalendarSource).where(SchoolCalendarSource.calendar_id == calendar_id,
        SchoolCalendarSource.sha256 == original.sha256))).first()
    if copy is None:
        copy = SchoolCalendarSource(calendar_id=calendar_id, filename=original.filename, sha256=original.sha256,
            size=original.size, content=original.content, page_count=original.page_count, pages=original.pages,
            truncated=original.truncated, uploaded_by=original.uploaded_by)
        db.add(copy); await db.flush()
    return copy.id


async def next_number(db, calendar_id):
    return ((await db.exec(select(func.max(SchoolCalendarRevision.number)).where(
        SchoolCalendarRevision.calendar_id == calendar_id))).one() or 0) + 1


def draft_for_edit(revision, expected_version):
    if revision.state != 'draft':
        raise HTTPException(409, 'Published calendars cannot change. Create a new draft from it')
    if revision.version != expected_version:
        raise HTTPException(409, 'This draft changed. Reload it before saving')


# --- Class schedules -------------------------------------------------------

def session_dto(row, superseded=False):
    return {'id': row.id, 'slot_key': row.slot_key, 'starts_at': row.starts_at, 'ends_at': row.ends_at,
            'title': row.title, 'state': row.state, 'week_number': row.academic_week, 'rotation': row.rotation,
            'nominal_date': row.nominal_on, 'makeup_for': row.nominal_on if row.calendar_kind == 'makeup' else None,
            'mode': row.mode, 'location': row.location, 'note': row.note, 'calendar_kind': row.calendar_kind,
            'superseded': superseded, 'version': row.version, 'timezone': row.timezone,
            'attendance_url': f'/attendance?class={row.class_id}&session={row.id}'}


async def class_sessions(db, class_id):
    rows = (await db.exec(select(AttendanceSession).where(AttendanceSession.class_id == class_id)
                          .order_by(AttendanceSession.starts_at, AttendanceSession.id))).all()
    replaced = {r.replaces_session_id for r in rows if r.replaces_session_id}
    return rows, replaced


async def heads(db, class_id):
    """Current version of each calendar meeting keyed by (kind, week, slot)."""
    rows, replaced = await class_sessions(db, class_id)
    successor = {r.replaces_session_id: r for r in rows if r.replaces_session_id}
    result = {}
    for row in rows:
        if row.calendar_kind and row.replaces_session_id is None:
            head = row
            while head.id in successor:
                head = successor[head.id]
            result[(row.calendar_kind, row.academic_week, row.slot_key)] = head
    evidence = set((await db.exec(select(AttendanceChallenge.session_id).where(
        AttendanceChallenge.session_id.in_([r.id for r in rows] or [-1])))).all())
    return result, evidence


async def schedule_dto(db, cls, schedule, manageable):
    rows, replaced = await class_sessions(db, cls.id) if cls else ([], set())
    revision = await db.get(SchoolCalendarRevision, schedule.revision_id) if schedule else None
    calendar = await db.get(SchoolCalendar, revision.calendar_id) if revision else None
    newer = None
    if revision:
        newer = (await db.exec(select(func.max(SchoolCalendarRevision.id)).where(
            SchoolCalendarRevision.calendar_id == revision.calendar_id, SchoolCalendarRevision.state == 'published',
            SchoolCalendarRevision.id > revision.id))).one()
    return {'class_id': cls.id if cls else None, 'version': schedule.version if schedule else 0,
            'manageable': manageable, 'revision_id': revision.id if revision else None,
            'calendar_name': calendar.name if calendar else None, 'pattern': schedule.pattern if schedule else '',
            'newer_revision_id': newer, 'sessions': [session_dto(r, r.id in replaced) for r in rows]}


def _same(head, row):
    return all(getattr(head, k) == row[k] for k in _COMPARED)


async def preview(db, cls, schedule, revision, payload, facts, pattern, now):
    """Diff of the reviewed plan against saved sessions; never writes."""
    label = f"{facts['course_code']} {facts['section']}"
    rows, warnings, errors = planner.plan(payload, facts['semester'], facts['meetings'], pattern, label)
    current, evidence = await heads(db, cls.id) if cls else ({}, set())
    planned_keys, actions = set(), []
    for row in rows:
        key = (row['calendar_kind'], row['academic_week'], row['slot_key'])
        planned_keys.add(key)
        head = current.get(key)
        if head is None:
            action = 'skipped_past' if row['starts_at'] <= now else 'added'
        elif _same(head, row):
            action = 'unchanged'
        elif head.starts_at <= now or head.id in evidence or row['starts_at'] <= now:
            action = 'protected'
        else:
            action = 'replaced'
        actions.append((action, row, head))
    for key, head in sorted(current.items(), key=lambda item: (item[1].starts_at, item[1].id)):
        if key in planned_keys or head.state == 'no_class':
            continue
        protected = head.starts_at <= now or head.id in evidence
        actions.append(('protected' if protected else 'cancelled', None, head))
    if cls is not None:
        # Manual sessions stay untouched; teachers resolve clashes from their saved attendance links.
        manual = (await db.exec(select(AttendanceSession).where(AttendanceSession.class_id == cls.id,
            AttendanceSession.calendar_kind.is_(None), AttendanceSession.state == 'scheduled'))).all()
        for action, row, _ in actions:
            if row is None or row['state'] != 'scheduled' or action not in ('added', 'replaced', 'unchanged'):
                continue
            for other in manual:
                if row['starts_at'] < other.ends_at and other.starts_at < row['ends_at']:
                    warnings = sorted({*warnings, f"Week {row['academic_week']} meeting overlaps saved session #{other.id} \"{other.title}\""})
    skipped = sum(a == 'skipped_past' for a, _, _ in actions)
    if skipped:
        warnings = sorted({*warnings, f'{skipped} meetings are already in the past and will not be created'})
    protected = sum(a == 'protected' for a, _, _ in actions)
    if protected:
        warnings = sorted({*warnings, f'{protected} past or recorded meetings are kept unchanged'})
    version = schedule.version if schedule else 0
    material = {'class_id': cls.id if cls else None, 'class_version': cls.version if cls else None,
                'schedule_version': version, 'revision_id': revision.id, 'payload': revision.payload,
                'source_id': revision.source_id, 'pattern': pattern, 'facts': facts,
                'actions': [(a, r, h and (h.id, h.version, h.state, h.id in evidence)) for a, r, h in actions]}
    sessions = []
    for action, row, head in actions:
        # Show the actual post-apply result: kept heads stay as saved; cancelled become no_class.
        if row is None or action == 'protected':
            item = {**session_dto(head), 'action': action}
            if action == 'cancelled':
                item['state'] = 'no_class'
        else:
            item = {'id': head.id if head is not None and action == 'unchanged' else None,
                    'slot_key': row['slot_key'], 'starts_at': row['starts_at'], 'ends_at': row['ends_at'],
                    'title': row['title'], 'state': row['state'], 'week_number': row['academic_week'],
                    'rotation': row['rotation'], 'nominal_date': row['nominal_on'], 'makeup_for': row['makeup_for'],
                    'mode': row['mode'], 'location': row['location'], 'note': row['note'],
                    'calendar_kind': row['calendar_kind'], 'timezone': row['timezone'], 'superseded': False,
                    'attendance_url': None, 'action': action}
        sessions.append(item)
    sessions.sort(key=lambda s: (s['starts_at'], s['slot_key'] or ''))
    count = lambda *names: sum(a in names for a, _, _ in actions)
    return {'fingerprint': planner.fingerprint(material), 'sessions': sessions, 'warnings': warnings,
            'errors': errors, 'protected_count': protected,
            'changes': {'added': count('added'), 'replaced': count('replaced'), 'cancelled': count('cancelled'),
                        'unchanged': count('unchanged'), 'skipped_past': skipped},
            'version': version}, actions


def _state(db, row, actor_id, state, reason):
    before = row.state
    row.state = state
    row.version += 1
    db.add(row)
    db.add(AttendanceEvent(session_id=row.id, actor_user_id=actor_id, kind='session_state_changed',
                           details={'from': before, 'to': state, 'reason': reason, 'version': row.version,
                                    'source': 'calendar_schedule'}))


async def apply(db, cls, actions, actor_id, revision_id):
    """Execute reviewed actions inside the caller's locked transaction."""
    inserted = 0
    for action, row, head in actions:
        if action == 'cancelled':
            _state(db, head, actor_id, 'no_class', 'Removed from the reviewed class schedule')
        elif action == 'replaced' and row is not None:
            if row['state'] != head.state and all(getattr(head, k) == row[k] for k in _COMPARED if k not in ('state',)):
                _state(db, head, actor_id, row['state'], 'Reviewed calendar schedule')
                continue
            if head.state == 'scheduled':
                _state(db, head, actor_id, 'no_class', 'Replaced by a reviewed calendar schedule')
            await db.flush()
            inserted += await _insert(db, cls, row, actor_id, revision_id, head.id)
        elif action == 'added':
            inserted += await _insert(db, cls, row, actor_id, revision_id, None)
    return inserted


async def _insert(db, cls, row, actor_id, revision_id, replaces):
    session = AttendanceSession(class_id=cls.id, created_by=actor_id, replaces_session_id=replaces,
        **{k: row[k] for k in ('title', 'starts_at', 'ends_at', 'timezone', 'state', 'calendar_kind',
                               'academic_week', 'slot_key', 'nominal_on', 'rotation', 'mode', 'location', 'note')})
    db.add(session)
    await db.flush()
    db.add(AttendanceEvent(session_id=session.id, actor_user_id=actor_id, kind='session_created',
        details={'source': 'calendar_schedule', 'revision_id': revision_id, 'replaces_session_id': replaces,
                 'calendar_kind': session.calendar_kind, 'academic_week': session.academic_week,
                 'slot_key': session.slot_key, 'starts_at': session.starts_at.isoformat(),
                 'ends_at': session.ends_at.isoformat(), 'state': session.state}))
    return 1


async def section_class(db, facts, org_id):
    rows = (await db.exec(select(AcademicClass).where(
        AcademicClass.registry_course_id == facts['registry_course_id'], AcademicClass.academic_year == facts['academic_year'],
        AcademicClass.semester == facts['semester'], AcademicClass.section == facts['section']))).all()
    if len(rows) > 1:
        raise HTTPException(409, 'This official section has ambiguous class history; ask an administrator to review')
    if rows:
        await roster.class_course(db, rows[0], org_id)
        return rows[0]
    return None


__all__ = [name for name in globals() if not name.startswith("__")]
