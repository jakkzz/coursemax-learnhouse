"""Private subject ownership; never embed this data in public User projections.

Identity rows reserve subjects permanently. Native user deletion is restricted;
eligible deletion/anonymization needs the separate lifecycle/retention policy.
The same PostgreSQL guards are installed by create_all and the migration.
"""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, DDL, ForeignKey, Index, Integer, UniqueConstraint, event, text
from sqlmodel import Field, SQLModel


class ProviderIdentity(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("provider", "issuer", "namespace", "subject", name="uq_provider_identity_subject"),
        CheckConstraint("(provider = 'google' AND issuer = 'https://accounts.google.com' AND namespace = 'global') OR (provider = 'line' AND issuer = 'https://access.line.me')", name="ck_provider_identity_issuer"),
        CheckConstraint("length(trim(namespace)) > 0 AND length(trim(subject)) > 0", name="ck_provider_identity_nonempty"),
        CheckConstraint("(retired_at IS NULL AND retirement_reason IS NULL) OR (retired_at IS NOT NULL AND retirement_reason IS NOT NULL AND length(trim(retirement_reason)) > 0)", name="ck_provider_identity_retirement"),
        Index("uq_provider_identity_active_user", "user_id", "provider", unique=True, postgresql_where=text("retired_at IS NULL")),
    )
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(sa_column=Column(Integer, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False))
    provider: str = Field(max_length=16)
    issuer: str = Field(max_length=128)
    namespace: str = Field(max_length=128)
    subject: str = Field(max_length=255, repr=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
    retired_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    retirement_reason: str | None = Field(default=None, max_length=500, repr=False)


class ProviderIdentityEvent(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("kind IN ('bound', 'retired')", name="ck_provider_identity_event_kind"),
        CheckConstraint("length(trim(reason)) > 0", name="ck_provider_identity_event_reason"),
    )
    id: int | None = Field(default=None, primary_key=True)
    identity_id: int = Field(sa_column=Column(Integer, ForeignKey("provideridentity.id", ondelete="RESTRICT"), nullable=False))
    actor_user_id: int = Field(sa_column=Column(Integer, ForeignKey("user.id", ondelete="RESTRICT"), nullable=False))
    kind: str = Field(max_length=16)
    reason: str = Field(max_length=500, repr=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))


# Keep the migration's frozen copy aligned. Separate statements also work with
# asyncpg, which deliberately refuses multiple commands in one prepared statement.
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
for table, statements in ((ProviderIdentity.__table__, GUARD_DDL), (ProviderIdentityEvent.__table__, EVENT_GUARD_DDL)):
    for statement in statements:
        event.listen(table, "after_create", DDL(statement).execute_if(dialect="postgresql"))

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
