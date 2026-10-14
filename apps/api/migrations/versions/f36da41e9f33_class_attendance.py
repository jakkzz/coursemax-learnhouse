"""Add class attendance sessions and retained scan receipts; no backfill."""
from alembic import op
from src.db.class_attendance import ATTENDANCE_TABLES
revision = 'f36da41e9f33'
down_revision = 'f25c930d8e22'
branch_labels = None
depends_on = None


def upgrade():
    for table in ATTENDANCE_TABLES:
        table.create(op.get_bind(), checkfirst=True)


def downgrade():
    raise RuntimeError('Attendance evidence must be retained; disable access instead')
