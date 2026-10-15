"""Explicit administrator review/apply, using the existing native session only."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError

from src.route66_ext.adapters.core_events_database import get_db_session
from src.route66_ext.db.academic_classes import AcademicClass
from src.route66_ext.routers.school_identity import context, private
from src.route66_ext.routers.google_subject_auth import boundary
from src.route66_ext.services import academic_rosters, learning_access

router = APIRouter()


class AccessApply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_id: int = Field(gt=0, strict=True)
    enabled: StrictBool
    confirm_changes: StrictBool
    expected_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("reason")
    @classmethod
    def meaningful_reason(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError("A meaningful reason is required")
        return value


async def _class(db, user, org_id, class_id):
    if user.is_superadmin is not True:
        raise HTTPException(403, "Platform administrator approval required for learning access")
    cls = await db.get(AcademicClass, class_id)
    if cls is None:
        raise HTTPException(404, "Class not found")
    await academic_rosters.can_manage(db, user, cls, org_id)
    return cls


@router.get("/{class_id}/learning-access/preview")
async def preview(class_id: int, request: Request, response: Response,
                  group_id: int = Query(gt=0), enabled: bool = True,
                  db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, _ = await context(request, db)
    cls = await _class(db, user, config.org_id, class_id)
    return await learning_access.preview(db, user.id, cls, config.org_id, group_id, enabled)


@router.post("/{class_id}/learning-access/apply")
async def apply(class_id: int, body: AccessApply, request: Request, response: Response,
                db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, _ = await context(request, db)
    boundary(request, config)
    if body.confirm_changes is not True:
        raise HTTPException(400, "Review and confirm native learning access changes")
    cls = await _class(db, user, config.org_id, class_id)
    try:
        result = await learning_access.apply(db, user.id, cls, config.org_id,
            **body.model_dump(exclude={"confirm_changes"}))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Native access changed. Review a fresh preview") from None
    return result
