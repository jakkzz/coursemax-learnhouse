"""Native email uniqueness prevents concurrent mixed-method account collisions.

Revision: d84e13a6b902; parent: c71a02d9ef40.
No merging/deletion/backfill. Duplicate legacy rows stop the migration for review.
"""
from alembic import op
import sqlalchemy as sa

revision = 'd84e13a6b902'
down_revision = 'c71a02d9ef40'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    op.execute('LOCK TABLE "user" IN SHARE ROW EXCLUSIVE MODE')
    duplicates = bind.execute(sa.text('SELECT EXISTS (SELECT 1 FROM "user" GROUP BY lower(email) HAVING count(*) > 1)')).scalar()
    if duplicates:
        raise RuntimeError('Native email collisions require reviewed resolution; no accounts were changed')
    existing = bind.execute(sa.text(
        "SELECT i.indisunique AND i.indisvalid AND i.indnkeyatts=1 "
        "AND i.indpred IS NULL AND i.indrelid='\"user\"'::regclass "
        "AND pg_get_indexdef(i.indexrelid,1,true) IN ('lower(email)', 'lower(email::text)', 'lower((email)::text)') "
        "FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname=current_schema() AND c.relname='uq_user_email_lower'"
    )).scalar()
    if existing is not None:
        if existing is not True:
            raise RuntimeError('Native email index needs review')
    else:
        op.execute('CREATE UNIQUE INDEX uq_user_email_lower ON "user" (lower(email))')


def downgrade():
    # Removing the index while Google registration is available reintroduces a
    # race and cannot be treated as a routine application-image rollback.
    raise RuntimeError('Email uniqueness downgrade requires a separately reviewed auth cutover')

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
