"""Class-owned session schedules and immutable QR scan receipts/events."""
from datetime import date, datetime, timezone
from sqlalchemy import Column, Date, DateTime, CheckConstraint, ForeignKey, Index, Integer, SmallInteger, UniqueConstraint, DDL, event, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field


def now():
    return datetime.now(timezone.utc)


class AttendanceSession(SQLModel, table=True):
    __table_args__ = (CheckConstraint("ends_at > starts_at AND grace_minutes >= 0 AND late_threshold_minutes >= grace_minutes AND state IN ('scheduled','no_class') AND version >= 0", name='ck_attendance_session'),
        # Calendar meetings: one root per (week, slot, kind); each version has one successor.
        CheckConstraint("calendar_kind IS NULL OR (calendar_kind IN ('regular','makeup') AND academic_week IS NOT NULL AND slot_key IS NOT NULL AND nominal_on IS NOT NULL)", name='ck_attendance_calendar_meeting'),
        Index('uq_attendance_calendar_root', 'class_id', 'academic_week', 'slot_key', 'calendar_kind', unique=True,
              postgresql_where=text('calendar_kind IS NOT NULL AND replaces_session_id IS NULL')),
        Index('uq_attendance_replacement', 'replaces_session_id', unique=True,
              postgresql_where=text('replaces_session_id IS NOT NULL')),)
    id: int | None = Field(default=None, primary_key=True)
    class_id: int = Field(foreign_key='academicclass.id', index=True)
    title: str = Field(max_length=160)
    starts_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    ends_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    timezone: str = Field(default='Asia/Bangkok', max_length=80)
    grace_minutes: int = 10
    late_threshold_minutes: int = 20
    state: str = 'scheduled'
    version: int = 0
    created_by: int = Field(foreign_key='user.id')
    # Insert-only calendar provenance (NULL for manually created sessions).
    calendar_kind: str | None = Field(default=None, max_length=20)
    academic_week: int | None = Field(default=None, sa_column=Column(SmallInteger))
    slot_key: str | None = Field(default=None, max_length=40)
    nominal_on: date | None = Field(default=None, sa_column=Column(Date))
    replaces_session_id: int | None = Field(default=None, sa_column=Column(Integer, ForeignKey('attendancesession.id')))
    rotation: str | None = Field(default=None, max_length=20)
    mode: str | None = Field(default=None, max_length=20)
    location: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=500)


class AttendanceChallenge(SQLModel, table=True):
    __table_args__ = (CheckConstraint("kind IN ('entry','heartbeat') AND expires_at > created_at", name='ck_attendance_challenge'),)
    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key='attendancesession.id', index=True)
    token_hash: str = Field(max_length=64, unique=True)
    session_version: int
    kind: str
    created_at: datetime = Field(default_factory=now, sa_column=Column(DateTime(timezone=True), nullable=False))
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    created_by: int = Field(foreign_key='user.id')


class AttendanceScan(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint('challenge_id', 'roster_entry_id', name='uq_attendance_scan_challenge_roster'),
        CheckConstraint("computed_status IN ('present','late') AND kind IN ('entry','heartbeat')", name='ck_attendance_scan'),)
    id: int | None = Field(default=None, primary_key=True)
    receipt_id: str = Field(max_length=36, unique=True)
    session_id: int = Field(foreign_key='attendancesession.id', index=True)
    challenge_id: int = Field(foreign_key='attendancechallenge.id')
    roster_entry_id: int = Field(foreign_key='academicrosterentry.id', index=True)
    actor_user_id: int = Field(foreign_key='user.id')
    arrived_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    kind: str
    computed_status: str


class AttendanceEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key='attendancesession.id', index=True)
    actor_user_id: int = Field(foreign_key='user.id')
    kind: str = Field(max_length=60)
    details: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    created_at: datetime = Field(default_factory=now, sa_column=Column(DateTime(timezone=True), nullable=False))


CALENDAR_COLUMNS = ('calendar_kind', 'academic_week', 'slot_key', 'nominal_on', 'replaces_session_id', 'rotation', 'mode', 'location', 'note')
ATTENDANCE_TABLES = tuple(m.__table__ for m in (AttendanceSession, AttendanceChallenge, AttendanceScan, AttendanceEvent))
IMMUTABLE_FUNCTION = """CREATE OR REPLACE FUNCTION lh_attendance_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Attendance evidence is immutable'; END; $$"""
SESSION_FUNCTION = """CREATE OR REPLACE FUNCTION lh_attendance_schedule_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Attendance sessions must be retained'; END IF;
 IF ROW(NEW.class_id,NEW.title,NEW.starts_at,NEW.ends_at,NEW.timezone,NEW.grace_minutes,NEW.late_threshold_minutes,NEW.created_by,
 NEW.calendar_kind,NEW.academic_week,NEW.slot_key,NEW.nominal_on,NEW.replaces_session_id,NEW.rotation,NEW.mode,NEW.location,NEW.note)
 IS DISTINCT FROM ROW(OLD.class_id,OLD.title,OLD.starts_at,OLD.ends_at,OLD.timezone,OLD.grace_minutes,OLD.late_threshold_minutes,OLD.created_by,
 OLD.calendar_kind,OLD.academic_week,OLD.slot_key,OLD.nominal_on,OLD.replaces_session_id,OLD.rotation,OLD.mode,OLD.location,OLD.note)
 THEN RAISE EXCEPTION 'Attendance schedule cannot be rewritten'; END IF;
 RETURN NEW;
END; $$"""
SCAN_SCOPE_FUNCTION = """CREATE OR REPLACE FUNCTION lh_attendance_scan_scope() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM attendancechallenge c JOIN attendancesession s ON s.id=c.session_id
 JOIN academicrosterentry r ON r.class_id=s.class_id
 WHERE c.id=NEW.challenge_id AND s.id=NEW.session_id AND r.id=NEW.roster_entry_id AND c.kind=NEW.kind)
 THEN RAISE EXCEPTION 'Attendance scan belongs to another class, session or challenge'; END IF;
 RETURN NEW;
END; $$"""
SCAN_SCOPE_TRIGGER = 'CREATE TRIGGER lh_attendance_scan_scope BEFORE INSERT ON attendancescan FOR EACH ROW EXECUTE FUNCTION lh_attendance_scan_scope()'
GUARDS = [IMMUTABLE_FUNCTION, SESSION_FUNCTION]
for table in ATTENDANCE_TABLES:
    name = table.name
    function = 'lh_attendance_schedule_immutable' if name == 'attendancesession' else 'lh_attendance_immutable'
    statements = [f'CREATE TRIGGER lh_{name}_immutable BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION {function}()',
                  f'CREATE TRIGGER lh_{name}_no_truncate BEFORE TRUNCATE ON {name} FOR EACH STATEMENT EXECUTE FUNCTION lh_attendance_immutable()']
    GUARDS.extend(statements)
    # Functions must precede triggers, including create_all bootstrapping.
    for statement in [IMMUTABLE_FUNCTION, SESSION_FUNCTION, *statements]:
        event.listen(table, 'after_create', DDL(statement).execute_if(dialect='postgresql'))
for statement in (SCAN_SCOPE_FUNCTION, SCAN_SCOPE_TRIGGER):
    GUARDS.append(statement)
    event.listen(AttendanceScan.__table__, 'after_create', DDL(statement).execute_if(dialect='postgresql'))

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
