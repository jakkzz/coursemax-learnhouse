"""Manager-only operational status; no source fetch and no roster side effects on GET."""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.route66_ext.adapters.core_events_database import get_db_session
from src.route66_ext.db.academic_classes import AcademicClassEvent
from src.route66_ext.db.roster_refresh import AcademicRosterRefresh
from src.route66_ext.routers.academic_classes import staff_class, commit
from src.route66_ext.routers.school_identity import context, private
from src.route66_ext.routers.google_subject_auth import boundary, resources, throttle
from src.route66_ext.services import academic_rosters as roster, roster_refresh as service

router = APIRouter()


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    paused: StrictBool
    expected_version: int = Field(ge=0)


@router.get('/{class_id}/roster/refresh')
async def status(class_id: int, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, _ = await context(request, db)
    cls = await staff_class(db, user, config.org_id, class_id)
    state = await db.get(AcademicRosterRefresh, class_id)
    events = (await db.exec(select(AcademicClassEvent).where(AcademicClassEvent.class_id == class_id,
        AcademicClassEvent.kind == 'roster_refresh_finished').order_by(AcademicClassEvent.id.desc()).limit(3))).all()
    now = service.utcnow()
    checking = bool(state and state.lease_id and state.lease_until and state.lease_until > now)
    return {'class_id': class_id, 'class_version': cls.version,
        'control_version': state.control_version if state else 0,
        'paused': state.paused if state else False, 'initial_review_required': cls.last_synced_at is None,
        'status': 'checking' if checking else 'retrying' if state and state.status == 'checking' else state.status if state else 'ready',
        'last_attempt_at': state.last_attempt_at if state else None,
        'last_accepted_at': cls.last_synced_at,
        'next_check_at': state.next_check_at if state and not state.paused and cls.last_synced_at else None,
        'delayed': bool(state and not state.paused and state.next_check_at < now - timedelta(minutes=5) and not checking),
        'recent': [{'id': e.id, 'at': e.created_at, 'origin': e.details.get('origin'),
                    'outcome': e.details.get('outcome'), 'counts': e.details.get('counts')} for e in events]}


@router.post('/{class_id}/roster/refresh/check', status_code=202)
async def check(class_id: int, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, _ = await context(request, db)
    boundary(request, config)
    await roster.serialize(db)
    cls = await staff_class(db, user, config.org_id, class_id)
    async with resources(config) as (redis, _):
        await throttle(redis, request, config, 'roster-check-' + str(user.id))
    if not await service.authorised(db, cls, config.org_id):
        raise HTTPException(409, 'Review the initial roster or restore this class teaching assignment before checking')
    now = service.utcnow()
    state = await service.state_for(db, cls, now=now)
    if state.paused:
        raise HTTPException(409, 'Resume automatic checks, or review a fresh roster while paused')
    checking = state.lease_id and state.lease_until and state.lease_until > now
    if not checking and state.status != 'queued':
        state.status, state.next_check_at = 'queued', now
        db.add(state)
        roster.event(db, user.id, 'roster_refresh_requested', {}, cls)
    await commit(db)
    return {'status': 'checking' if checking else 'queued'}


@router.post('/{class_id}/roster/refresh/settings')
async def settings(class_id: int, body: Settings, request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    private(response)
    user, config, _ = await context(request, db)
    boundary(request, config)
    await roster.serialize(db)
    cls = await staff_class(db, user, config.org_id, class_id)
    state = await service.state_for(db, cls)
    if state.control_version != body.expected_version:
        raise HTTPException(409, 'Check settings changed. Reload the status and try again')
    if state.paused != body.paused:
        state.paused = body.paused
        state.control_version += 1
        state.lease_id = state.lease_until = None
        state.status = 'ready'
        if not state.paused:
            state.next_check_at = service.utcnow()
        db.add(state)
        roster.event(db, user.id, 'roster_refresh_settings_changed', {'paused': state.paused,
            'control_version': state.control_version}, cls)
    await commit(db)
    return {'paused': state.paused, 'control_version': state.control_version}
