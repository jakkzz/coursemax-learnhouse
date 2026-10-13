"""Private, one-time optional profile import state; never a user-editable blob."""
from datetime import datetime
from sqlalchemy import CheckConstraint, Column, DateTime
from sqlmodel import Field, SQLModel

class ProviderProfileImport(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("status IN ('pending','busy','complete','failed','skipped','cancelled')", name='ck_profile_import_status'),
        CheckConstraint('attempts >= 0 AND attempts <= 3', name='ck_profile_import_attempts'),
    )
    user_id: int = Field(primary_key=True, foreign_key='user.id')
    identity_id: int | None = Field(default=None, foreign_key='provideridentity.id')
    status: str = Field(default='pending', max_length=16)
    attempts: int = 0
    picture_url: str | None = Field(default=None, max_length=2048, repr=False)
    display_name: str | None = Field(default=None, max_length=160, repr=False)
    locale_hint: str | None = Field(default=None, max_length=2)
    lease_until: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
