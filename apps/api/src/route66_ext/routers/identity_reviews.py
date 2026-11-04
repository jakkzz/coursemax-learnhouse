"""Private student requests and the existing administrator's identity-review queue."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import String, cast, exists
from sqlalchemy.orm import aliased
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.route66_ext.adapters.core_events_database import get_db_session
from src.route66_ext.db.academic_classes import AcademicClass, AcademicClassEvent
from src.route66_ext.routers.google_subject_auth import boundary
from src.route66_ext.routers.school_identity import context, private
from src.route66_ext.services import academic_rosters as roster, identity_reviews as reviews

router = APIRouter()
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]


class ReviewBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: Reason


class Decision(ReviewBody):
    action: Literal['recheck', 'close']
    expected_token: str = Field(pattern=r'^[0-9a-f]{64}$')


@router.get('/identity-reviews/own')
async def own(request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, evidence = await context(request, db)
    profile = await reviews.own_profile(db, user.id, config.org_id, evidence)
    cases = (await db.exec(reviews.scoped(config.org_id).where(
        AcademicClassEvent.class_id.is_(None), AcademicClassEvent.actor_user_id == user.id)
        .order_by(AcademicClassEvent.id.desc()).limit(20))).all()
    open_case = None
    for case in cases:
        if profile and case.student_id == profile.id and await reviews.decision(db, case) is None:
            open_case = case.id
            break
    return {'can_request': profile is not None, 'open_case_id': open_case, 'cases': [await reviews.view(db, c, config.org_id) for c in cases]}


@router.post('/identity-reviews/own')
async def request_own(body: ReviewBody, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, evidence = await context(request, db)
    boundary(request, config)
    await roster.serialize(db)
    # Evidence is selected again after serialization, as in the login/roster writer.
    user, config, evidence = await context(request, db)
    if evidence is not None:
        await db.refresh(evidence)
    profile = await reviews.own_profile(db, user.id, config.org_id, evidence)
    if profile is None:
        raise HTTPException(409, 'No saved roster record can be reviewed yet. Sign in with your school Google account or wait for the reviewed class roster.')
    case = await reviews.request_review(db, user.id, config.org_id, profile, body.reason)
    await db.commit()
    return await reviews.view(db, case, config.org_id)


@router.get('/identity-reviews')
async def inbox(request: Request, response: Response, status: Literal['open', 'closed'] = Query(default='open'),
                db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, _ = await context(request, db)
    if not user.is_superadmin:
        raise HTTPException(403, 'Administrator review required')
    resolution = aliased(AcademicClassEvent)
    resolved = exists(select(resolution.id).where(resolution.kind == reviews.DECISION,
        resolution.details['case_id'].as_string() == cast(AcademicClassEvent.id, String)))
    query = reviews.scoped(config.org_id).where(resolved if status == 'closed' else ~resolved)
    query = query.order_by(AcademicClassEvent.id.desc() if status == 'closed' else AcademicClassEvent.id)
    cases = (await db.exec(query.limit(100))).all()
    return {'cases': [await reviews.view(db, c, config.org_id, reviewer=True) for c in cases]}


@router.get('/identity-reviews/{case_id}')
async def detail(case_id: int, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, _ = await context(request, db)
    if not user.is_superadmin:
        raise HTTPException(403, 'Administrator review required')
    return await reviews.view(db, await reviews.get_case(db, case_id, config.org_id), config.org_id, reviewer=True)


@router.post('/identity-reviews/{case_id}/decision')
async def decide(case_id: int, body: Decision, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, _ = await context(request, db)
    boundary(request, config)
    if not user.is_superadmin:
        raise HTTPException(403, 'Administrator review required')
    await roster.serialize(db)
    case = await reviews.get_case(db, case_id, config.org_id)
    result = await reviews.decide(db, user.id, config.org_id, case, body.action, body.reason, body.expected_token)
    await db.commit()
    return result


@router.get('/{class_id}/identity-reviews')
async def class_reviews(class_id: int, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, _ = await context(request, db)
    cls = await db.get(AcademicClass, class_id)
    if cls is None:
        raise HTTPException(404, 'Class not found')
    await roster.can_manage(db, user, cls, config.org_id)
    cases = (await db.exec(reviews.scoped(config.org_id).where(AcademicClassEvent.class_id == cls.id)
        .order_by(AcademicClassEvent.id.desc()).limit(50))).all()
    return {'cases': [await reviews.view(db, c, config.org_id, manager=True) for c in cases]}
