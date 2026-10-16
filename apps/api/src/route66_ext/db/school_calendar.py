"""Shared school academic calendars and per-class schedule selection.

Source PDFs are retained byte-for-byte (private, not native public content).
Published revisions are immutable; classes pin one revision explicitly and a
newer revision never rewrites a class schedule without its own reviewed apply.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, LargeBinary, UniqueConstraint, CheckConstraint, DDL, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field


def now():
    return datetime.now(timezone.utc)


class SchoolCalendar(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('org_id', 'academic_year', 'track', name='uq_school_calendar_track'),
        CheckConstraint('academic_year BETWEEN 2500 AND 2700', name='ck_school_calendar_year'),)
    id: int | None = Field(default=None, primary_key=True)
    org_id: int = Field(foreign_key='organization.id', index=True)
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


CALENDAR_TABLES = tuple(m.__table__ for m in (SchoolCalendar, SchoolCalendarSource, SchoolCalendarRevision, ClassSchedule))

SOURCE_FUNCTION = """CREATE OR REPLACE FUNCTION lh_calendar_source_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Calendar source documents are retained unchanged'; END; $$"""
REVISION_FUNCTION = """CREATE OR REPLACE FUNCTION lh_calendar_revision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Calendar revisions are retained'; END IF;
 IF OLD.state = 'published' THEN RAISE EXCEPTION 'Published calendar revisions are immutable'; END IF;
 IF ROW(NEW.calendar_id,NEW.number,NEW.source_id,NEW.created_by) IS DISTINCT FROM ROW(OLD.calendar_id,OLD.number,OLD.source_id,OLD.created_by)
 THEN RAISE EXCEPTION 'Calendar revision identity cannot change'; END IF;
 RETURN NEW;
END; $$"""
GUARDS = {
    SchoolCalendarSource.__table__: [SOURCE_FUNCTION,
        'CREATE TRIGGER lh_calendar_source_immutable BEFORE UPDATE OR DELETE ON schoolcalendarsource FOR EACH ROW EXECUTE FUNCTION lh_calendar_source_immutable()',
        'CREATE TRIGGER lh_calendar_source_no_truncate BEFORE TRUNCATE ON schoolcalendarsource FOR EACH STATEMENT EXECUTE FUNCTION lh_calendar_source_immutable()'],
    SchoolCalendarRevision.__table__: [REVISION_FUNCTION,
        'CREATE TRIGGER lh_calendar_revision_guard BEFORE UPDATE OR DELETE ON schoolcalendarrevision FOR EACH ROW EXECUTE FUNCTION lh_calendar_revision_guard()',
        'CREATE TRIGGER lh_calendar_revision_no_truncate BEFORE TRUNCATE ON schoolcalendarrevision FOR EACH STATEMENT EXECUTE FUNCTION lh_calendar_source_immutable()'],
}
for table, statements in GUARDS.items():
    # The revision truncate guard reuses the source function; create it first.
    for statement in ([SOURCE_FUNCTION] if table is SchoolCalendarRevision.__table__ else []) + statements:
        event.listen(table, 'after_create', DDL(statement).execute_if(dialect='postgresql'))

__all__ = [name for name in globals() if not name.startswith("__")]
