"""Operational scheduling only; roster and immutable events remain their authorities."""
from datetime import datetime
from sqlalchemy import Column, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import SQLModel, Field


class AcademicRosterRefresh(SQLModel, table=True):
    __tablename__ = 'academicrosterrefresh'
    __table_args__ = (CheckConstraint('control_version >= 0', name='ck_roster_refresh_version'),)
    class_id: int = Field(primary_key=True, foreign_key='academicclass.id')
    paused: bool = False
    control_version: int = 0
    next_check_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
    last_attempt_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    last_semantic_hash: str | None = Field(default=None, max_length=64)
    result_event_id: int | None = Field(default=None, foreign_key='academicclassevent.id')
    status: str = Field(default='ready', max_length=40)
    lease_id: str | None = Field(default=None, max_length=32)
    lease_until: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    approved_drop: dict | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
