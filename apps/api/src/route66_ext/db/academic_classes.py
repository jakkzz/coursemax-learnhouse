"""Bounded academic authority: teaching assignments, offerings and roster identities.

These records never change native roles, content authorship or historical work.
All mutations append AcademicClassEvent in the same transaction; no delete API.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field

def now(): return datetime.now(timezone.utc)

class CourseRegistryBinding(SQLModel, table=True):
    course_id: int = Field(primary_key=True, foreign_key='course.id')
    registry_course_id: str = Field(max_length=20)
    course_code: str = Field(max_length=30)

class TeachingAssignment(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('course_id','user_id',name='uq_teaching_course_user'),)
    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key='course.id', index=True)
    user_id: int = Field(foreign_key='user.id', index=True)
    active: bool = True

class AcademicClass(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint('registry_class_id','academic_year','semester',name='uq_official_class_term'),
        UniqueConstraint('course_id','academic_year','semester','section',name='uq_course_section_term'),
        UniqueConstraint('registry_course_id','academic_year','semester','section',name='uq_official_course_section_term'),
        CheckConstraint('semester BETWEEN 1 AND 3 AND academic_year BETWEEN 2500 AND 2700',name='ck_class_term'),)
    id: int | None = Field(default=None, primary_key=True)
    # Organization owns the school class; a native course is an optional match.
    # Database trigger derives/validates org_id from course_id for legacy callers.
    org_id: int | None = Field(default=None, sa_column=Column(Integer, ForeignKey('organization.id'), nullable=False, index=True))
    course_id: int | None = Field(default=None, foreign_key='course.id', index=True)
    teacher_user_id: int | None = Field(default=None, foreign_key='user.id')
    registry_title: str | None = Field(default=None, max_length=300)
    academic_year: int
    semester: int
    section: str = Field(max_length=40)
    registry_course_id: str = Field(max_length=20)
    registry_class_id: str | None = Field(default=None, max_length=20)
    registry_course_code: str = Field(max_length=30)
    version: int = 0
    last_source_hash: str | None = Field(default=None, max_length=64)
    last_synced_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))

class SchoolStudent(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('student_number',name='uq_school_student_number'),
        UniqueConstraint('user_id',name='uq_school_student_user'),
        CheckConstraint("student_number IS NULL OR student_number ~ '^[0-9]{10}$'",name='ck_school_student_number'),)
    id: int | None = Field(default=None, primary_key=True)
    student_number: str | None = Field(default=None, max_length=10)
    has_registry_evidence: bool = False
    user_id: int | None = Field(default=None, foreign_key='user.id')
    identity_id: int | None = Field(default=None, foreign_key='provideridentity.id')
    full_name_th: str = Field(max_length=200)
    faculty: str = Field(max_length=200)
    program: str = Field(max_length=200)

class AcademicRosterEntry(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('class_id','student_id',name='uq_class_student'),
        CheckConstraint("status IN ('active','withdrawn') AND source IN ('registry','manual') AND missing_count >= 0",name='ck_roster_state'),)
    id: int | None = Field(default=None, primary_key=True)
    class_id: int = Field(foreign_key='academicclass.id', index=True)
    student_id: int = Field(foreign_key='schoolstudent.id', index=True)
    status: str = 'active'
    source: str = 'registry'
    registry_status_code: str | None = Field(default=None,max_length=80)
    missing_count: int = 0
    display_position: int

class AcademicClassEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    class_id: int | None = Field(default=None, foreign_key='academicclass.id', index=True)
    student_id: int | None = Field(default=None, foreign_key='schoolstudent.id')
    actor_user_id: int = Field(foreign_key='user.id')
    kind: str = Field(max_length=80)
    details: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    created_at: datetime = Field(default_factory=now, sa_column=Column(DateTime(timezone=True), nullable=False))

ACADEMIC_TABLES = (CourseRegistryBinding.__table__, TeachingAssignment.__table__, AcademicClass.__table__, SchoolStudent.__table__, AcademicRosterEntry.__table__, AcademicClassEvent.__table__)

# Bootstrap uses the same append-only guard as the migration.
from sqlalchemy import DDL, event
EVENT_FUNCTION = """CREATE OR REPLACE FUNCTION lh_academic_event_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Academic class events are append-only'; END; $$"""
EVENT_TRIGGER = 'CREATE TRIGGER lh_academic_event_immutable BEFORE UPDATE OR DELETE ON academicclassevent FOR EACH ROW EXECUTE FUNCTION lh_academic_event_immutable()'
for statement in (EVENT_FUNCTION, EVENT_TRIGGER):
    event.listen(AcademicClassEvent.__table__, 'after_create', DDL(statement).execute_if(dialect='postgresql'))
# School-class organization is fixed; a native course match may be attached once
# (NULL -> course in the same organization) but never moved to another course.
CLASS_ORG_FUNCTION = """CREATE OR REPLACE FUNCTION lh_academic_class_org() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE course_org integer;
BEGIN
 IF NEW.course_id IS NOT NULL THEN
  SELECT org_id INTO course_org FROM course WHERE id=NEW.course_id;
  IF NEW.org_id IS NULL THEN NEW.org_id := course_org; END IF;
  IF course_org IS DISTINCT FROM NEW.org_id THEN RAISE EXCEPTION 'Class course belongs to another organization'; END IF;
 END IF;
 IF TG_OP = 'UPDATE' THEN
  IF NEW.org_id IS DISTINCT FROM OLD.org_id THEN RAISE EXCEPTION 'Class organization cannot change'; END IF;
  IF OLD.course_id IS NOT NULL AND NEW.course_id IS DISTINCT FROM OLD.course_id THEN RAISE EXCEPTION 'Class course match cannot be reassigned'; END IF;
 END IF;
 RETURN NEW;
END; $$"""
CLASS_ORG_TRIGGER = 'CREATE TRIGGER lh_academic_class_org BEFORE INSERT OR UPDATE ON academicclass FOR EACH ROW EXECUTE FUNCTION lh_academic_class_org()'
for statement in (CLASS_ORG_FUNCTION, CLASS_ORG_TRIGGER):
    event.listen(AcademicClass.__table__, 'after_create', DDL(statement).execute_if(dialect='postgresql'))

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
