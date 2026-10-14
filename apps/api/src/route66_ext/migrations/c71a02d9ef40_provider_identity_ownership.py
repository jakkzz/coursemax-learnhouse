"""Private provider subject ownership, permanent retirement and append-only events.

Revision ID: c71a02d9ef40
Revises: b6e199d023f8

Supports native create_all-first bootstrap. No identities are inferred/imported.
Downgrade is allowed only while both new tables are empty.
"""
from alembic import op
import re
import sqlalchemy as sa

revision = "c71a02d9ef40"
down_revision = "b6e199d023f8"
branch_labels = None
depends_on = None

# Frozen copy of the model's PostgreSQL DDL: migration history must not import
# current application models, whose definitions can change in a future release.
GUARD_DDL = (
    """CREATE OR REPLACE FUNCTION guard_provider_identity() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP IN ('DELETE', 'TRUNCATE') THEN
        RAISE EXCEPTION 'provider identities must be retained';
      END IF;
      IF ROW(NEW.id, NEW.user_id, NEW.provider, NEW.issuer, NEW.namespace, NEW.subject, NEW.created_at)
         IS DISTINCT FROM ROW(OLD.id, OLD.user_id, OLD.provider, OLD.issuer, OLD.namespace, OLD.subject, OLD.created_at)
         OR OLD.retired_at IS NOT NULL OR NEW.retired_at IS NULL THEN
        RAISE EXCEPTION 'provider identity ownership is immutable';
      END IF;
      RETURN NEW;
    END $$""",
    "DROP TRIGGER IF EXISTS provider_identity_guard ON provideridentity",
    "CREATE TRIGGER provider_identity_guard BEFORE UPDATE OR DELETE ON provideridentity FOR EACH ROW EXECUTE FUNCTION guard_provider_identity()",
    "DROP TRIGGER IF EXISTS provider_identity_no_truncate ON provideridentity",
    "CREATE TRIGGER provider_identity_no_truncate BEFORE TRUNCATE ON provideridentity FOR EACH STATEMENT EXECUTE FUNCTION guard_provider_identity()",
)
EVENT_GUARD_DDL = (
    """CREATE OR REPLACE FUNCTION guard_provider_identity_event() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'provider identity events are append-only'; END $$""",
    "DROP TRIGGER IF EXISTS provider_identity_event_guard ON provideridentityevent",
    "CREATE TRIGGER provider_identity_event_guard BEFORE UPDATE OR DELETE ON provideridentityevent FOR EACH ROW EXECUTE FUNCTION guard_provider_identity_event()",
    "DROP TRIGGER IF EXISTS provider_identity_event_no_truncate ON provideridentityevent",
    "CREATE TRIGGER provider_identity_event_no_truncate BEFORE TRUNCATE ON provideridentityevent FOR EACH STATEMENT EXECUTE FUNCTION guard_provider_identity_event()",
)


def upgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("provideridentity"):
        op.create_table(
            "provideridentity",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("provider", sa.String(16), nullable=False),
            sa.Column("issuer", sa.String(128), nullable=False),
            sa.Column("namespace", sa.String(128), nullable=False),
            sa.Column("subject", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("retired_at", sa.DateTime(timezone=True)),
            sa.Column("retirement_reason", sa.String(500)),
            sa.UniqueConstraint("provider", "issuer", "namespace", "subject", name="uq_provider_identity_subject"),
            sa.CheckConstraint("(provider = 'google' AND issuer = 'https://accounts.google.com' AND namespace = 'global') OR (provider = 'line' AND issuer = 'https://access.line.me')", name="ck_provider_identity_issuer"),
            sa.CheckConstraint("length(btrim(namespace)) > 0 AND length(btrim(subject)) > 0", name="ck_provider_identity_nonempty"),
            sa.CheckConstraint("(retired_at IS NULL AND retirement_reason IS NULL) OR (retired_at IS NOT NULL AND retirement_reason IS NOT NULL AND length(btrim(retirement_reason)) > 0)", name="ck_provider_identity_retirement"),
        )
        op.create_index("uq_provider_identity_active_user", "provideridentity", ["user_id", "provider"], unique=True, postgresql_where=sa.text("retired_at IS NULL"))
    if not sa.inspect(bind).has_table("provideridentityevent"):
        op.create_table(
            "provideridentityevent",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("identity_id", sa.Integer(), sa.ForeignKey("provideridentity.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("reason", sa.String(500), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("kind IN ('bound', 'retired')", name="ck_provider_identity_event_kind"),
            sa.CheckConstraint("length(btrim(reason)) > 0", name="ck_provider_identity_event_reason"),
        )
    # Fail closed on a partial/foreign pre-existing schema rather than silently
    # claiming uniqueness/retirement protections that are not installed.
    inspector = sa.inspect(bind)
    constraints = {x['name'] for x in inspector.get_check_constraints('provideridentity')}
    unique = {x['name']: x for x in inspector.get_unique_constraints('provideridentity')}
    indexes = {x['name']: x for x in inspector.get_indexes('provideridentity')}
    active = indexes.get('uq_provider_identity_active_user', {})
    predicate = re.sub(r'[()\s]', '', active.get('dialect_options', {}).get('postgresql_where', '')).lower()
    event_checks = {x['name'] for x in inspector.get_check_constraints('provideridentityevent')}
    if (
        not {'ck_provider_identity_issuer', 'ck_provider_identity_nonempty', 'ck_provider_identity_retirement'} <= constraints
        or unique.get('uq_provider_identity_subject', {}).get('column_names') != ['provider', 'issuer', 'namespace', 'subject']
        or not active.get('unique') or active.get('column_names') != ['user_id', 'provider']
        or predicate != 'retired_atisnull'
        or not {'ck_provider_identity_event_kind', 'ck_provider_identity_event_reason'} <= event_checks
    ):
        raise RuntimeError('Provider identity schema mismatch')
    for statement in GUARD_DDL + EVENT_GUARD_DDL:
        op.execute(statement)


def downgrade():
    bind = op.get_bind()
    existing = [table for table in ('provideridentity', 'provideridentityevent') if sa.inspect(bind).has_table(table)]
    if existing:
        # Fence concurrent inserts before checking emptiness; a mere SELECT then
        # DROP could otherwise erase a binding committed between the two.
        op.execute('LOCK TABLE ' + ', '.join(existing) + ' IN ACCESS EXCLUSIVE MODE')
    for table in existing:
        if bind.execute(sa.text(f'SELECT EXISTS (SELECT 1 FROM {table})')).scalar():
            raise RuntimeError('Cannot downgrade retained provider identities or events')
    for table in ('provideridentityevent', 'provideridentity'):
        if sa.inspect(bind).has_table(table):
            op.drop_table(table)
    op.execute('DROP FUNCTION IF EXISTS guard_provider_identity_event()')
    op.execute('DROP FUNCTION IF EXISTS guard_provider_identity()')

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
