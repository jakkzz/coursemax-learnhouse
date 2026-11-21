"""School-owned classes, shared academic calendars and calendar meeting provenance.

Revision ID: b3e9c4d1a702
Revises: f47eb52fa044

Existing class IDs, sessions, receipts and roster rows are preserved. The only
row write is the deterministic organization backfill from each class's course.
Attendance immutability is widened to the new provenance columns, never weakened.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

from src.route66_ext.db.academic_classes import CLASS_ORG_FUNCTION, CLASS_ORG_TRIGGER
from src.route66_ext.db.class_attendance import SESSION_FUNCTION
from src.route66_ext.db.school_calendar import CALENDAR_TABLES, GUARDS

revision = "b3e9c4d1a702"
down_revision = "f47eb52fa044"
branch_labels = None
depends_on = None

_SESSION_COLUMNS = (
    ("calendar_kind", sa.String(length=20)), ("academic_week", sa.SmallInteger()),
    ("slot_key", sa.String(length=40)), ("nominal_on", sa.Date()),
    ("replaces_session_id", sa.Integer()), ("rotation", sa.String(length=20)),
    ("mode", sa.String(length=20)), ("location", sa.String(length=1000)), ("note", sa.String(length=500)),
)
_CLASS_COLUMNS = (("org_id", sa.Integer()), ("teacher_user_id", sa.Integer()), ("registry_title", sa.String(length=300)))


def _names(rows):
    return {row["name"] for row in rows}


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    # Every preflight read precedes every schema modification.
    orphan = connection.execute(text("""
        SELECT c.id FROM academicclass c LEFT JOIN course k ON k.id = c.course_id
         WHERE c.course_id IS NOT NULL AND k.id IS NULL LIMIT 1""")).first()
    if orphan is not None:
        raise RuntimeError("Refusing migration: a class references a missing course; preserve it for review")
    class_columns = _names(inspector.get_columns("academicclass"))
    session_columns = _names(inspector.get_columns("attendancesession"))
    session_checks = _names(inspector.get_check_constraints("attendancesession"))
    session_indexes = _names(inspector.get_indexes("attendancesession"))
    session_fks = {tuple(fk["constrained_columns"]) for fk in inspector.get_foreign_keys("attendancesession")}
    class_fks = {tuple(fk["constrained_columns"]) for fk in inspector.get_foreign_keys("academicclass")}
    class_indexes = _names(inspector.get_indexes("academicclass"))
    course_nullable = next(c["nullable"] for c in inspector.get_columns("academicclass") if c["name"] == "course_id")

    for name, kind in _CLASS_COLUMNS:
        if name not in class_columns:
            op.add_column("academicclass", sa.Column(name, kind, nullable=True))
    op.execute("""UPDATE academicclass c SET org_id = k.org_id FROM course k
                   WHERE c.org_id IS NULL AND k.id = c.course_id""")
    op.alter_column("academicclass", "org_id", nullable=False, existing_type=sa.Integer())
    if ("org_id",) not in class_fks:
        op.create_foreign_key("fk_academicclass_org", "academicclass", "organization", ["org_id"], ["id"])
    if ("teacher_user_id",) not in class_fks:
        op.create_foreign_key("fk_academicclass_teacher", "academicclass", "user", ["teacher_user_id"], ["id"])
    if "ix_academicclass_org_id" not in class_indexes:
        op.create_index("ix_academicclass_org_id", "academicclass", ["org_id"])
    if not course_nullable:
        op.alter_column("academicclass", "course_id", nullable=True, existing_type=sa.Integer())
    op.execute(CLASS_ORG_FUNCTION)
    op.execute("DROP TRIGGER IF EXISTS lh_academic_class_org ON academicclass")
    op.execute(CLASS_ORG_TRIGGER)

    for name, kind in _SESSION_COLUMNS:
        if name not in session_columns:
            op.add_column("attendancesession", sa.Column(name, kind, nullable=True))
    if ("replaces_session_id",) not in session_fks:
        op.create_foreign_key("fk_attendancesession_replaces", "attendancesession", "attendancesession",
                              ["replaces_session_id"], ["id"])
    if "ck_attendance_calendar_meeting" not in session_checks:
        op.create_check_constraint("ck_attendance_calendar_meeting", "attendancesession",
            "calendar_kind IS NULL OR (calendar_kind IN ('regular','makeup') AND academic_week IS NOT NULL "
            "AND slot_key IS NOT NULL AND nominal_on IS NOT NULL)")
    if "uq_attendance_calendar_root" not in session_indexes:
        op.create_index("uq_attendance_calendar_root", "attendancesession",
            ["class_id", "academic_week", "slot_key", "calendar_kind"], unique=True,
            postgresql_where=text("calendar_kind IS NOT NULL AND replaces_session_id IS NULL"))
    if "uq_attendance_replacement" not in session_indexes:
        op.create_index("uq_attendance_replacement", "attendancesession", ["replaces_session_id"], unique=True,
            postgresql_where=text("replaces_session_id IS NOT NULL"))
    # Same function name; existing triggers now also freeze the provenance columns.
    op.execute(SESSION_FUNCTION)

    for table in CALENDAR_TABLES:
        table.create(connection, checkfirst=True)
    for statements in GUARDS.values():
        for statement in statements:
            if statement.startswith("CREATE TRIGGER "):
                name, table = statement.split()[2], statement.split(" ON ")[1].split()[0]
                op.execute(f"DROP TRIGGER IF EXISTS {name} ON {table}")
            op.execute(statement)


def downgrade():
    raise RuntimeError("School classes, calendars and attendance provenance must be retained; disable access instead")
