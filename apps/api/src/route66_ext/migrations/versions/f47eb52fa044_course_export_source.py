"""Allow URL-free course exports and enforce one official course section.

Revision ID: f47eb52fa044
Revises: f36da41e9f33
"""
from alembic import op
from sqlalchemy import String, text

revision = "f47eb52fa044"
down_revision = "f36da41e9f33"
branch_labels = None
depends_on = None

_OFFICIAL_UNIQUE = "uq_official_course_section_term"


def _duplicate_official_tuple(connection):
    return connection.execute(text("""
        SELECT registry_course_id, academic_year, semester, section, count(*)
          FROM academicclass
         GROUP BY registry_course_id, academic_year, semester, section
        HAVING count(*) > 1
         LIMIT 1
    """)).first()


def _constraint_exists(connection):
    return connection.execute(text("""
        SELECT 1
          FROM pg_constraint
         WHERE conrelid = 'academicclass'::regclass AND conname = :name
    """), {"name": _OFFICIAL_UNIQUE}).first() is not None


def upgrade():
    connection = op.get_bind()
    duplicate = _duplicate_official_tuple(connection)
    if duplicate is not None:
        raise RuntimeError(
            "Refusing migration: duplicate official course/year/semester/section "
            "tuples must be reviewed without reassigning history"
        )
    constraint_exists = _constraint_exists(connection)
    # Every preflight read intentionally precedes every schema modification.
    op.alter_column("academicclass", "registry_class_id", nullable=True,
                    existing_type=String(length=20))
    # Fresh databases can already have this constraint because the historical
    # table-creation revision uses registered model metadata.
    if not constraint_exists:
        op.create_unique_constraint(_OFFICIAL_UNIQUE, "academicclass",
            ["registry_course_id", "academic_year", "semester", "section"])


def downgrade():
    connection = op.get_bind()
    if connection.execute(text(
            "SELECT 1 FROM academicclass WHERE registry_class_id IS NULL LIMIT 1"
        )).first() is not None:
        raise RuntimeError(
            "Refusing downgrade: URL-free classes have no registry class ID"
        )
    op.drop_constraint(_OFFICIAL_UNIQUE, "academicclass", type_="unique")
    op.alter_column("academicclass", "registry_class_id", nullable=False,
                    existing_type=String(length=20))
