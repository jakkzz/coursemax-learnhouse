"""Explicit administrator review/apply, using the existing native session only."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from src.route66_ext.db.academic_classes import AcademicClassEvent

from src.route66_ext.adapters.core_events_database import get_db_session
from src.route66_ext.db.academic_classes import AcademicClass
from src.route66_ext.routers.school_identity import context, private
from src.route66_ext.routers.google_subject_auth import boundary
from src.route66_ext.services import academic_rosters, learning_access

router = APIRouter()


class AccessApply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_id: int | None = Field(default=None, gt=0, strict=True)
    replace_group: StrictBool = False
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
    unmatched(cls)
    return cls


def unmatched(cls):
    if cls.course_id is None:
        raise HTTPException(409, "Connect this school class to a native course before configuring learning access")


@router.get("/{class_id}/learning-access/preview")
async def preview(class_id: int, request: Request, response: Response,
                  group_id: int | None = Query(default=None, gt=0), enabled: bool = True, replace_group: bool = False,
                  db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, _ = await context(request, db)
    cls = await _class(db, user, config.org_id, class_id)
    return await learning_access.preview(db, user.id, cls, config.org_id, group_id, enabled, replace_group)


@router.get("/{class_id}/learning-access/status")
async def status(class_id: int, request: Request, response: Response,
                 db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, _ = await context(request, db)
    cls = await db.get(AcademicClass, class_id)
    if cls is None: raise HTTPException(404, "Class not found")
    await academic_rosters.can_manage(db, user, cls, config.org_id)
    if cls.course_id is None: return {"status": "not_matched", "can_configure": False}
    try:
        binding = await learning_access._binding(db, cls.course_id)
        if binding is None: return {"status": "not_configured", "can_configure": user.is_superadmin is True}
        if not binding["enabled"]: return {"status": "disabled", "can_configure": user.is_superadmin is True}
        await learning_access.native.inspect_group(db, cls.course_id, config.org_id, binding["group_id"])
        events = (await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.kind.in_(
            ["learning_access_pending", "learning_access_ready"])).order_by(AcademicClassEvent.id.desc()))).all()
        last = next((e for e in events if e.details.get("course_id") == cls.course_id), None)
        return {"status": "needs_repair" if last and last.kind == "learning_access_pending" else "ready",
                "can_configure": user.is_superadmin is True}
    except (HTTPException, ValueError):
        return {"status": "needs_repair", "can_configure": user.is_superadmin is True}


@router.post("/{class_id}/learning-access/retry")
async def retry(class_id: int, request: Request, response: Response,
                db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, _ = await context(request, db); boundary(request, config)
    await academic_rosters.serialize(db)
    cls = await db.get(AcademicClass, class_id)
    if cls is None: raise HTTPException(404, "Class not found")
    await academic_rosters.can_manage(db, user, cls, config.org_id)
    unmatched(cls)
    result = await learning_access.refresh_course(db, user.id, cls.course_id)
    if result["status"] == "not_configured":
        db.add(AcademicClassEvent(actor_user_id=user.id, class_id=cls.id, kind="learning_access_pending",
            details={"course_id": cls.course_id, "reason": "configuration_requested"}))
        result = {"status": "requested", "removed_count": 0}
    await db.commit()
    return result


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
