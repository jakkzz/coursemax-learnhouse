"""Private Google evidence and self-confirmed NRRU directory association.

Neither table grants administration, authorship, enrollment or course assignment.
Directory confirmation is self-attestation, not institutional approval.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlmodel import Field, SQLModel

class SchoolGoogleEvidence(SQLModel, table=True):
    identity_id: int = Field(primary_key=True, foreign_key='provideridentity.id')
    user_id: int = Field(foreign_key='user.id', index=True)
    email: str = Field(max_length=320, repr=False)
    hosted_domain: str | None = Field(default=None, max_length=255)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))

class NrruTeacherIdentity(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('officer_id', name='uq_nrru_teacher_officer'),)
    user_id: int = Field(primary_key=True, foreign_key='user.id')
    identity_id: int = Field(foreign_key='provideridentity.id')
    officer_id: str = Field(max_length=20)
    officer_code: str = Field(max_length=20)
    name_th: str = Field(max_length=200)
    name_en: str = Field(max_length=200)
    confirmed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column=Column(DateTime(timezone=True), nullable=False))
