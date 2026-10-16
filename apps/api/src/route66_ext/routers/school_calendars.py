"""Shared school academic calendars and reviewed class schedules.

Publishing shared calendars uses the existing bounded platform-administrator
check. Class schedules use the teacher's own verified registrar section, and
never grant native roles, enrollment, authorship or learning access.
"""
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import logging
from pathlib import PurePath
from typing import Literal
from urllib.parse import quote
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.route66_ext.adapters.core_events_database import get_db_session
from src.route66_ext.db.academic_classes import AcademicClass
from src.route66_ext.db.school_calendar import SchoolCalendar, SchoolCalendarSource, SchoolCalendarRevision, ClassSchedule
from src.route66_ext.routers.school_identity import context, private
from src.route66_ext.routers.google_subject_auth import boundary
from src.route66_ext.routers.class_connections import Section, SectionQuery, verified_section
from src.route66_ext.services import academic_rosters as roster
from src.route66_ext.services import calendar_plan as planner
from src.route66_ext.services import class_attendance as attendance
from src.route66_ext.services import school_calendar as service

router = APIRouter()
log = logging.getLogger(__name__)


class _Body(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SaveDraft(_Body):
    expected_version: StrictInt = Field(ge=0)
    payload: dict


class Versioned(_Body):
    expected_version: StrictInt = Field(ge=0)


class Publish(Versioned):
    reviewed: StrictBool


class NewDraft(_Body):
    from_revision_id: StrictInt = Field(gt=0)


class SchedulePreview(_Body):
    section: Section
    revision_id: StrictInt = Field(gt=0)
    pattern: Literal['onsite', 'online', 'even_onsite']
    expected_version: StrictInt | None = Field(default=None, ge=0)


class ScheduleApply(SchedulePreview):
    expected_version: StrictInt = Field(ge=0)
    fingerprint: str = Field(pattern=r'^[a-f0-9]{64}$')
    reviewed: StrictBool


def administrator(user):
    if user.is_superadmin is not True:
        raise HTTPException(403, 'Platform administrator approval required to edit shared school calendars')


async def commit(db):
    from src.route66_ext.routers.academic_classes import commit as checked
    await checked(db)


# --- Shared calendar library -----------------------------------------------

@router.get('')
async def calendars(request: Request, response: Response, year: int | None = None,
                    db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, _ = await context(request, db)
    query = select(SchoolCalendar).where(SchoolCalendar.org_id == config.org_id)
    if year is not None:
        query = query.where(SchoolCalendar.academic_year == year)
    rows = (await db.exec(query.order_by(SchoolCalendar.academic_year.desc(), SchoolCalendar.track))).all()
    items = [await service.calendar_summary(db, c) for c in rows]
    editor = user.is_superadmin is True
    return {'can_edit': editor, 'calendars': [c for c in items if editor or c['published_revision_id']]}


def _pdf_facts(data):
    from pypdf import PdfReader
    from src.route66_ext.adapters.services_ai_rag_formats import pdf_pages
    try:
        page_count = len(PdfReader(BytesIO(data)).pages)
    except Exception:
        raise HTTPException(422, {'code': 'invalid_pdf', 'message': 'This file is not a readable PDF'}) from None
    pages = pdf_pages(data, max_chars=service.MAX_TEXT_CHARS)
    truncated = sum(len(text) for _, text in pages) >= service.MAX_TEXT_CHARS
    return page_count, [{'page': n, 'text': text} for n, text in pages], truncated


@router.post('')
async def upload(request: Request, response: Response, name: str = Form(min_length=1, max_length=200),
                 academic_year: int = Form(ge=2500, le=2700), track: str = Form(min_length=1, max_length=40),
                 file: UploadFile = File(...), db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, _ = await context(request, db); boundary(request, config); administrator(user)
    # Calendar group is a natural Thai/English label (for example ภาคปกติ), not a code.
    track, name = ' '.join(track.split()), ' '.join(name.split())
    if not track or not name:
        raise HTTPException(422, {'code': 'invalid_calendar', 'message': 'Enter the calendar name and group'})
    data = await file.read(service.MAX_PDF_BYTES + 1)
    if len(data) > service.MAX_PDF_BYTES:
        raise HTTPException(413, {'code': 'too_large', 'message': 'Upload a PDF up to 10 MB'})
    if not data.startswith(b'%PDF-'):
        raise HTTPException(422, {'code': 'invalid_pdf', 'message': 'Upload the academic calendar as a PDF'})
    page_count, pages, truncated = await asyncio.to_thread(_pdf_facts, data)
    digest = sha256(data).hexdigest()
    filename = PurePath(file.filename or 'calendar.pdf').name[:255] or 'calendar.pdf'
    await roster.serialize(db)
    calendar = (await db.exec(select(SchoolCalendar).where(SchoolCalendar.org_id == config.org_id,
        SchoolCalendar.academic_year == academic_year, SchoolCalendar.track == track))).first()
    if calendar is None:
        calendar = SchoolCalendar(org_id=config.org_id, academic_year=academic_year, track=track,
                                  name=name, created_by=user.id)
        db.add(calendar); await db.flush()
    source = (await db.exec(select(SchoolCalendarSource).where(SchoolCalendarSource.calendar_id == calendar.id,
        SchoolCalendarSource.sha256 == digest))).first()
    if source is None:
        source = SchoolCalendarSource(calendar_id=calendar.id, filename=filename, sha256=digest, size=len(data),
            content=data, page_count=page_count, pages=pages, truncated=truncated, uploaded_by=user.id)
        db.add(source); await db.flush()
    note = (f'{len(pages)} of {page_count} pages have selectable text. Read it automatically or complete the calendar manually.'
            if pages else 'No selectable text was found (scanned PDF?). Complete the calendar manually; the original PDF is kept.')
    if truncated:
        note += ' Text was shortened for very long documents; check the PDF itself.'
    revision = SchoolCalendarRevision(calendar_id=calendar.id, number=await service.next_number(db, calendar.id),
        payload=planner.empty_payload(), source_id=source.id, parse_note=note, created_by=user.id)
    db.add(revision); await db.flush()
    await commit(db)
    return await service.revision_dto(db, revision)


@router.get('/revisions/{revision_id}')
async def revision(revision_id: int, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, _ = await context(request, db)
    row, _ = await service.revision_in_org(db, revision_id, config.org_id, editor=user.is_superadmin is True)
    return await service.revision_dto(db, row)


@router.get('/revisions/{revision_id}/source')
async def source(revision_id: int, request: Request, db: AsyncSession = Depends(get_db_session)):
    user, config, _ = await context(request, db)
    row, _ = await service.revision_in_org(db, revision_id, config.org_id, editor=user.is_superadmin is True)
    document = await db.get(SchoolCalendarSource, row.source_id) if row.source_id else None
    if document is None:
        raise HTTPException(404, 'This revision has no source PDF')
    return Response(document.content, media_type='application/pdf', headers={
        'Content-Disposition': "inline; filename=\"calendar.pdf\"; filename*=UTF-8''" + quote(document.filename),
        'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff'})


@router.put('/revisions/{revision_id}')
async def save(revision_id: int, body: SaveDraft, request: Request, response: Response,
               db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, _ = await context(request, db); boundary(request, config); administrator(user)
    payload = service.payload_model(body.payload)
    await roster.serialize(db)
    row, _ = await service.revision_in_org(db, revision_id, config.org_id, editor=True)
    service.draft_for_edit(row, body.expected_version)
    row.payload = payload.model_dump(mode='json'); row.version += 1; db.add(row)
    await commit(db)
    return await service.revision_dto(db, row)


_PARSE_PROMPT = """You read a Thai university academic-calendar PDF and return only facts it states.
Use ISO Gregorian dates (Buddhist Era year minus 543). For each semester give term start/end,
every numbered week with start/end dates, and every class closure date with its make-up date
(null when the document gives no make-up). Rotation: use 'odd' or 'even' only when the document
explicitly labels the week; use 'midterm'/'final' for exam weeks and 'teaching' otherwise. Never
derive odd/even from week numbers. Set teaching=true for every week unless the document explicitly
states that regular classes do not meet that week. For an exam week without such an explicit
statement, keep teaching=true, set uncertain=true and add an 'unresolved' entry asking the reviewer
whether regular classes meet. Expand closure ranges into one row per date. Give the page number for each item. Mark anything ambiguous
with uncertain=true and describe it in 'unresolved'. Registration, payment and other events are
not closures. Do not invent missing values; leave lists empty instead."""


@router.post('/revisions/{revision_id}/parse')
async def parse(revision_id: int, body: Versioned, request: Request, response: Response,
                db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, _ = await context(request, db); boundary(request, config); administrator(user)
    row, calendar = await service.revision_in_org(db, revision_id, config.org_id, editor=True)
    service.draft_for_edit(row, body.expected_version)
    document = await db.get(SchoolCalendarSource, row.source_id) if row.source_id else None
    if document is None or not document.pages:
        raise HTTPException(422, {'code': 'no_text', 'message': 'This PDF has no selectable text to read automatically. Complete the calendar manually; the PDF is kept.'})
    from src.route66_ext.adapters.security_features_utils_usage import reserve_ai_credit, refund_ai_credit
    from src.route66_ext.adapters.services_security_rate_limiting import enforce_ai_rate_limit
    from src.route66_ext.adapters.security_org_auth import enforce_org_mfa
    from src.route66_ext.adapters.services_ai_llm import generate, resolve_model_for_org
    await enforce_org_mfa(user.id, config.org_id, db)
    enforce_ai_rate_limit(user.id, config.org_id)
    try:
        await reserve_ai_credit(config.org_id, db, amount=1)
    except HTTPException as error:
        if error.status_code != 403:
            raise
        raise HTTPException(403, {'code': 'ai_unavailable', 'message': f'{error.detail}. Complete the calendar manually; the PDF and draft are kept.'}) from None
    text = '\n\n'.join(f"--- Page {p['page']} ---\n{p['text']}" for p in document.pages)
    try:
        model = await resolve_model_for_org(config.org_id, db, purpose='planning')
        result = await generate(model_name=model, system_prompt=_PARSE_PROMPT, output_type=planner.Payload,
            user_prompt=f'Academic year (BE): {calendar.academic_year}. Calendar track: {calendar.track}.\n\n{text}', timeout=180)
        payload = planner.Payload.model_validate(result.model_dump() if hasattr(result, 'model_dump') else result)
    except Exception as error:
        refund_ai_credit(config.org_id, 1)
        if type(error).__name__ == 'AINotConfiguredError':
            raise HTTPException(403, {'code': 'ai_unavailable', 'message': 'Automatic reading is not configured. Complete the calendar manually; the PDF and draft are kept.'}) from None
        log.warning('Academic calendar parse failed for revision %s', revision_id, exc_info=True)
        raise HTTPException(502, {'code': 'parse_failed', 'message': 'Automatic reading failed. Retry, or complete the calendar manually; the PDF and draft are unchanged.'}) from None
    await roster.serialize(db)
    await db.refresh(row)
    if row.state != 'draft' or row.version != body.expected_version:
        refund_ai_credit(config.org_id, 1)
        raise HTTPException(409, 'This draft changed while it was being read. Reload it; nothing was overwritten.')
    found = planner.issues(payload, document.page_count)
    row.payload = payload.model_dump(mode='json'); row.version += 1
    row.parse_note = (f'Read automatically from {len(document.pages)} pages. Check every date against the PDF before publishing'
                      + (f'; {len(found)} items need review.' if found else '.'))[:1000]
    db.add(row)
    await commit(db)
    return await service.revision_dto(db, row)


@router.post('/revisions/{revision_id}/publish')
async def publish(revision_id: int, body: Publish, request: Request, response: Response,
                  db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, _ = await context(request, db); boundary(request, config); administrator(user)
    if body.reviewed is not True:
        raise HTTPException(400, 'Review every term, week and closure before publishing')
    await roster.serialize(db)
    row, _ = await service.revision_in_org(db, revision_id, config.org_id, editor=True)
    service.draft_for_edit(row, body.expected_version)
    document = await db.get(SchoolCalendarSource, row.source_id) if row.source_id else None
    found = planner.issues(service.payload_model(row.payload), document.page_count if document else None)
    if found:
        raise HTTPException(422, {'code': 'not_publishable', 'issues': found})
    row.state = 'published'; row.version += 1; row.published_by = user.id
    row.published_at = datetime.now(timezone.utc); db.add(row)
    await commit(db)
    return await service.revision_dto(db, row)


@router.post('/{calendar_id}/draft')
async def new_draft(calendar_id: int, body: NewDraft, request: Request, response: Response,
                    db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, _ = await context(request, db); boundary(request, config); administrator(user)
    await roster.serialize(db)
    base, calendar = await service.revision_in_org(db, body.from_revision_id, config.org_id, editor=True)
    if calendar.id != calendar_id:
        raise HTTPException(404, 'Calendar revision not found')
    row = SchoolCalendarRevision(calendar_id=calendar.id, number=await service.next_number(db, calendar.id),
        payload=base.payload, source_id=base.source_id, created_by=user.id,
        parse_note=f'Draft copied from revision {base.number}. Publishing it does not change any class until each class reviews it.')
    db.add(row); await db.flush()
    await commit(db)
    return await service.revision_dto(db, row)


# --- Class schedules --------------------------------------------------------

async def _manageable(db, user, cls, org_id):
    try:
        await roster.can_manage(db, user, cls, org_id)
        return True
    except HTTPException as error:
        if error.status_code != 403:
            raise
        return False


@router.get('/schedules')
async def schedule(request: Request, response: Response, body: SectionQuery = Depends(),
                   db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, evidence = await context(request, db)
    facts = body.model_dump()
    cls = await service.section_class(db, facts, config.org_id)
    if cls is not None and await _manageable(db, user, cls, config.org_id):
        return await service.schedule_dto(db, cls, await db.get(ClassSchedule, cls.id), True)
    # No managed class yet: only the teacher of this exact official section may set it up.
    await verified_section(db, user, config, evidence, body, request)
    if cls is not None:
        raise HTTPException(409, 'This section belongs to another teacher or course. Ask an administrator to review it.')
    return await service.schedule_dto(db, None, None, True)


@router.get('/schedules/by-class/{class_id}')
async def schedule_by_class(class_id: int, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, _ = await context(request, db)
    cls = await db.get(AcademicClass, class_id)
    if cls is None:
        raise HTTPException(404, 'Class not found')
    await roster.class_course(db, cls, config.org_id)  # organization scope before staff or student paths
    manageable = await _manageable(db, user, cls, config.org_id)
    if not manageable:
        await attendance.member(db, cls, user)
    return await service.schedule_dto(db, cls, await db.get(ClassSchedule, cls.id), manageable)


async def _prepare(db, user, config, evidence, body, request):
    facts = await verified_section(db, user, config, evidence, body.section, request, meetings=True)
    facts.pop('org_id', None)
    revision, calendar = await service.revision_in_org(db, body.revision_id, config.org_id)
    if calendar.academic_year != facts['academic_year']:
        raise HTTPException(409, f"Choose a calendar for academic year {facts['academic_year']}")
    return facts, revision


async def _state(db, user, config, facts, revision, pattern):
    cls = await service.section_class(db, facts, config.org_id)
    if cls is not None:
        await roster.can_manage(db, user, cls, config.org_id)
    schedule = await db.get(ClassSchedule, cls.id) if cls else None
    payload = service.payload_model(revision.payload)
    result, actions = await service.preview(db, cls, schedule, revision, payload, facts, pattern, datetime.now(timezone.utc))
    return cls, schedule, result, actions


@router.post('/schedules/preview')
async def schedule_preview(body: SchedulePreview, request: Request, response: Response,
                           db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, evidence = await context(request, db)
    facts, revision = await _prepare(db, user, config, evidence, body, request)
    _, schedule, result, _ = await _state(db, user, config, facts, revision, body.pattern)
    if body.expected_version is not None and body.expected_version != result['version']:
        raise HTTPException(409, 'This class schedule changed. Reload it before reviewing')
    return result


@router.post('/schedules/apply')
async def schedule_apply(body: ScheduleApply, request: Request, response: Response,
                         db: AsyncSession = Depends(get_db_session)):
    private(response); user, config, evidence = await context(request, db); boundary(request, config)
    if body.reviewed is not True:
        raise HTTPException(400, 'Review the dated meetings before saving this schedule')
    facts, revision = await _prepare(db, user, config, evidence, body, request)
    await roster.serialize(db)
    cls, schedule, result, actions = await _state(db, user, config, facts, revision, body.pattern)
    if schedule is not None and schedule.applied_fingerprint == body.fingerprint:
        return await service.schedule_dto(db, cls, schedule, True)
    if body.expected_version != result['version'] or body.fingerprint != result['fingerprint']:
        raise HTTPException(409, 'The schedule, calendar, roster or attendance changed. Preview it again; nothing was saved.')
    if result['errors']:
        raise HTTPException(422, {'code': 'schedule_errors', 'errors': result['errors']})
    if cls is None:
        # First save creates the school class from exact verified own-timetable facts.
        cls = AcademicClass(org_id=config.org_id, course_id=None, teacher_user_id=user.id,
            registry_title=facts['title'], registry_course_code=facts['course_code'],
            registry_course_id=facts['registry_course_id'], registry_class_id=None,
            academic_year=facts['academic_year'], semester=facts['semester'], section=facts['section'])
        db.add(cls); await db.flush()
        roster.event(db, user.id, 'class_created', {**facts, 'org_id': config.org_id, 'course_id': None,
            'setup': 'school_schedule'}, cls)
    inserted = await service.apply(db, cls, actions, user.id, revision.id)
    meetings = facts['meetings']
    if schedule is None:
        schedule = ClassSchedule(class_id=cls.id, revision_id=revision.id, pattern=body.pattern, meetings=meetings,
                                 version=1, applied_fingerprint=body.fingerprint, applied_by=user.id)
    else:
        schedule.revision_id, schedule.pattern, schedule.meetings = revision.id, body.pattern, meetings
        schedule.version += 1; schedule.applied_fingerprint = body.fingerprint; schedule.applied_by = user.id
        schedule.applied_at = datetime.now(timezone.utc)
    db.add(schedule)
    if inserted:
        cls.version += 1; db.add(cls)
    roster.event(db, user.id, 'class_schedule_applied', {'revision_id': revision.id, 'pattern': body.pattern,
        'fingerprint': body.fingerprint, 'changes': result['changes'], 'protected': result['protected_count'],
        'schedule_version': schedule.version}, cls)
    await commit(db)
    return await service.schedule_dto(db, cls, schedule, True)


__all__ = [name for name in globals() if not name.startswith("__")]
