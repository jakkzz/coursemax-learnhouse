"""Shared school academic calendars and per-class schedule selection.

Source PDFs are retained byte-for-byte (private, not native public content).
Published revisions are immutable; classes pin one revision explicitly and a
newer revision never rewrites a class schedule without its own reviewed apply.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, LargeBinary, UniqueConstraint, CheckConstraint, Index, DDL, event, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field


def now():
    return datetime.now(timezone.utc)


class SchoolCalendar(SQLModel, table=True):
    __table_args__ = (Index('uq_school_calendar_shared_track', 'org_id', 'academic_year', 'track', unique=True,
                           postgresql_where=text("scope = 'organization'")),
        CheckConstraint("(scope = 'organization' AND owner_user_id IS NULL) OR (scope = 'teacher' AND owner_user_id IS NOT NULL)", name='ck_school_calendar_scope'),
        CheckConstraint('academic_year BETWEEN 2500 AND 2700', name='ck_school_calendar_year'),)
    id: int | None = Field(default=None, primary_key=True)
    org_id: int = Field(foreign_key='organization.id', index=True)
    scope: str = Field(default='organization', max_length=20)
    owner_user_id: int | None = Field(default=None, foreign_key='user.id', index=True)
    academic_year: int
    track: str = Field(max_length=40)
    name: str = Field(max_length=200)
    created_by: int = Field(foreign_key='user.id')
    created_at: datetime = Field(default_factory=now, sa_column=Column(DateTime(timezone=True), nullable=False))


class SchoolCalendarSource(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('calendar_id', 'sha256', name='uq_school_calendar_source'),)
    id: int | None = Field(default=None, primary_key=True)
    calendar_id: int = Field(foreign_key='schoolcalendar.id', index=True)
    filename: str = Field(max_length=255)
    sha256: str = Field(max_length=64)
    size: int
    content: bytes = Field(sa_column=Column(LargeBinary, nullable=False), repr=False)
    page_count: int
    pages: list = Field(default_factory=list, sa_column=Column(JSONB, nullable=False), repr=False)
    truncated: bool = False
    uploaded_by: int = Field(foreign_key='user.id')
    created_at: datetime = Field(default_factory=now, sa_column=Column(DateTime(timezone=True), nullable=False))


class SchoolCalendarRevision(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('calendar_id', 'number', name='uq_school_calendar_revision'),
        CheckConstraint("state IN ('draft','published') AND version >= 0 AND number >= 1", name='ck_school_calendar_revision'),)
    id: int | None = Field(default=None, primary_key=True)
    calendar_id: int = Field(foreign_key='schoolcalendar.id', index=True)
    number: int
    state: str = 'draft'
    payload: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    source_id: int | None = Field(default=None, foreign_key='schoolcalendarsource.id')
    source_url: str | None = Field(default=None, max_length=2048)
    resolved_url: str | None = Field(default=None, max_length=2048)
    fetched_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    derived_from_revision_id: int | None = Field(default=None, foreign_key='schoolcalendarrevision.id')
    parse_note: str | None = Field(default=None, max_length=1000)
    version: int = 0
    created_by: int = Field(foreign_key='user.id')
    created_at: datetime = Field(default_factory=now, sa_column=Column(DateTime(timezone=True), nullable=False))
    published_by: int | None = Field(default=None, foreign_key='user.id')
    published_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class ClassSchedule(SQLModel, table=True):
    __table_args__ = (CheckConstraint("pattern IN ('onsite','online','even_onsite') AND version >= 1", name='ck_class_schedule'),)
    class_id: int = Field(primary_key=True, foreign_key='academicclass.id')
    revision_id: int = Field(foreign_key='schoolcalendarrevision.id', index=True)
    pattern: str = Field(max_length=20)
    meetings: list = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    version: int = 1
    applied_fingerprint: str = Field(max_length=64)
    applied_by: int = Field(foreign_key='user.id')
    applied_at: datetime = Field(default_factory=now, sa_column=Column(DateTime(timezone=True), nullable=False))


class SchoolCalendarAttachment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('request_event_id', 'calendar_revision_id', name='uq_school_calendar_attachment'),)
    id: int | None = Field(default=None, primary_key=True)
    request_event_id: int = Field(foreign_key='academicclassevent.id', index=True)
    calendar_revision_id: int = Field(foreign_key='schoolcalendarrevision.id')
    attached_by: int = Field(foreign_key='user.id')
    attached_at: datetime = Field(default_factory=now, sa_column=Column(DateTime(timezone=True), nullable=False))


CALENDAR_TABLES = tuple(m.__table__ for m in (SchoolCalendar, SchoolCalendarSource, SchoolCalendarRevision, ClassSchedule, SchoolCalendarAttachment))

SOURCE_FUNCTION = """CREATE OR REPLACE FUNCTION lh_calendar_source_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Calendar source documents are retained unchanged'; END; $$"""
REVISION_FUNCTION = """CREATE OR REPLACE FUNCTION lh_calendar_revision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Calendar revisions are retained'; END IF;
 IF OLD.state = 'published' THEN RAISE EXCEPTION 'Published calendar revisions are immutable'; END IF;
 IF ROW(NEW.calendar_id,NEW.number,NEW.source_id,NEW.created_by,NEW.source_url,NEW.resolved_url,NEW.fetched_at,NEW.derived_from_revision_id)
 IS DISTINCT FROM ROW(OLD.calendar_id,OLD.number,OLD.source_id,OLD.created_by,OLD.source_url,OLD.resolved_url,OLD.fetched_at,OLD.derived_from_revision_id)
 THEN RAISE EXCEPTION 'Calendar revision identity cannot change'; END IF;
 RETURN NEW;
END; $$"""
SCOPE_FUNCTION = """CREATE OR REPLACE FUNCTION lh_calendar_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF ROW(NEW.org_id,NEW.scope,NEW.owner_user_id) IS DISTINCT FROM ROW(OLD.org_id,OLD.scope,OLD.owner_user_id)
 THEN RAISE EXCEPTION 'Calendar ownership cannot change; copy a reviewed revision instead'; END IF;
 RETURN NEW;
END; $$"""
ATTACHMENT_FUNCTION = """CREATE OR REPLACE FUNCTION lh_calendar_attachment_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (
  SELECT 1 FROM academicclassevent e JOIN schoolcalendarrevision r ON r.id=NEW.calendar_revision_id
  JOIN schoolcalendar c ON c.id=r.calendar_id
  WHERE e.id=NEW.request_event_id AND e.kind='class_connection_requested' AND r.state='published'
   AND e.details->>'org_id'=c.org_id::text
   AND (c.scope='organization' OR c.owner_user_id=e.actor_user_id)
 ) THEN RAISE EXCEPTION 'Attach a reviewed calendar belonging to this proposal'; END IF;
 RETURN NEW;
END; $$"""
GUARDS = {
    SchoolCalendar.__table__: [SCOPE_FUNCTION,
        'CREATE TRIGGER lh_calendar_scope_guard BEFORE UPDATE ON schoolcalendar FOR EACH ROW EXECUTE FUNCTION lh_calendar_scope_guard()'],
    SchoolCalendarSource.__table__: [SOURCE_FUNCTION,
        'CREATE TRIGGER lh_calendar_source_immutable BEFORE UPDATE OR DELETE ON schoolcalendarsource FOR EACH ROW EXECUTE FUNCTION lh_calendar_source_immutable()',
        'CREATE TRIGGER lh_calendar_source_no_truncate BEFORE TRUNCATE ON schoolcalendarsource FOR EACH STATEMENT EXECUTE FUNCTION lh_calendar_source_immutable()'],
    SchoolCalendarRevision.__table__: [REVISION_FUNCTION,
        'CREATE TRIGGER lh_calendar_revision_guard BEFORE UPDATE OR DELETE ON schoolcalendarrevision FOR EACH ROW EXECUTE FUNCTION lh_calendar_revision_guard()',
        'CREATE TRIGGER lh_calendar_revision_no_truncate BEFORE TRUNCATE ON schoolcalendarrevision FOR EACH STATEMENT EXECUTE FUNCTION lh_calendar_source_immutable()'],
    SchoolCalendarAttachment.__table__: [SOURCE_FUNCTION, ATTACHMENT_FUNCTION,
        'CREATE TRIGGER lh_calendar_attachment_guard BEFORE INSERT ON schoolcalendarattachment FOR EACH ROW EXECUTE FUNCTION lh_calendar_attachment_guard()',
        'CREATE TRIGGER lh_calendar_attachment_immutable BEFORE UPDATE OR DELETE ON schoolcalendarattachment FOR EACH ROW EXECUTE FUNCTION lh_calendar_source_immutable()',
        'CREATE TRIGGER lh_calendar_attachment_no_truncate BEFORE TRUNCATE ON schoolcalendarattachment FOR EACH STATEMENT EXECUTE FUNCTION lh_calendar_source_immutable()'],
}
for table, statements in GUARDS.items():
    # The revision truncate guard reuses the source function; create it first.
    for statement in ([SOURCE_FUNCTION] if table is SchoolCalendarRevision.__table__ else []) + statements:
        event.listen(table, 'after_create', DDL(statement).execute_if(dialect='postgresql'))

__all__ = [name for name in globals() if not name.startswith("__")]
