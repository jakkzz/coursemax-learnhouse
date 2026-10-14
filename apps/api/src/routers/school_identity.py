"""Own-only NRRU directory association. No role, roster or course writers."""
import json
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.events.database import get_db_session
from src.db.provider_identity import ProviderIdentity
from src.db.school_identity import SchoolGoogleEvidence, NrruTeacherIdentity
from src.db.user_audit_events import UserAuditEvent
from src.db.user_organizations import UserOrganization
from src.db.users import PublicUser
from src.security.auth import get_current_user
from src.routers.google_subject_auth import settings, boundary, resources, throttle
from src.services.nrru_directory import teacher_hint, student_hint, search_directory, DirectoryUnavailable

router = APIRouter()
_CONSUME = "if redis.call('GET',KEYS[1]) == ARGV[1] then redis.call('DEL',KEYS[1]); return 1 end; return 0"
class Confirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    search_id: str = Field(pattern=r'^[A-Za-z0-9_-]{32,64}$')
    officer_id: str = Field(pattern=r'^[0-9]{1,20}$')
    confirm_own_name: bool

def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['Vary'] = 'Cookie, Authorization'

async def context(request, db):
    user = await get_current_user(request, db)
    if not isinstance(user, PublicUser):
        raise HTTPException(401, 'Sign in first')
    config = settings()
    member = (await db.exec(select(UserOrganization).where(UserOrganization.user_id == user.id, UserOrganization.org_id == config.org_id))).first()
    if member is None:
        raise HTTPException(403, 'Organization access required')
    evidence = (await db.exec(select(SchoolGoogleEvidence).join(ProviderIdentity, SchoolGoogleEvidence.identity_id == ProviderIdentity.id).where(
        SchoolGoogleEvidence.user_id == user.id, ProviderIdentity.user_id == user.id,
        ProviderIdentity.provider == 'google', ProviderIdentity.retired_at.is_(None)))).first()
    return user, config, evidence

def candidate(identity):
    return {k:getattr(identity,k) for k in ('officer_id','officer_code','name_th','name_en')}

def eligible(evidence):
    return teacher_hint(evidence.email, evidence.hosted_domain) if evidence else None

@router.get('/me')
async def own_identity(request:Request, response:Response, db:AsyncSession=Depends(get_db_session)):
    private(response)
    user, config, evidence = await context(request, db)
    hint = eligible(evidence)
    identity = await db.get(NrruTeacherIdentity, user.id)
    # Changed/retired Google evidence never preserves teacher eligibility.
    identity = identity if hint and identity and identity.identity_id == evidence.identity_id else None
    student_number = student_hint(evidence.email, evidence.hosted_domain) if evidence else None
    return {'eligible': bool(hint), 'search_hint': hint,
        'school_menu': bool(identity or student_number),
        'school_kind': 'staff' if identity else 'student' if student_number else None,
        'student_number_hint': student_number,
        'registrar_details_status': 'directory_confirmed' if identity else 'waiting_for_class_roster' if student_number else 'not_connected',
        'student_match_status': 'waiting_for_roster' if student_number else None,
        'needs_google_signin': evidence is None,
        'directory_identity': candidate(identity) if identity else None,
        'confirmation_kind': 'self_confirmed_directory' if identity else None,
        'courses': []}

@router.get('/timetable')
async def own_timetable(request:Request, response:Response,
    academic_year:int | None=Query(default=None), semester:int | None=Query(default=None),
    db:AsyncSession=Depends(get_db_session)):
    private(response)
    user, config, evidence = await context(request, db)
    identity = await db.get(NrruTeacherIdentity, user.id)
    if not eligible(evidence) or identity is None or identity.identity_id != evidence.identity_id:
        raise HTTPException(403, 'Confirm your own staff directory record first')
    from src.services.nrru_timetable import teacher_timetable
    from datetime import datetime, timezone
    async with resources(config) as (redis, _):
        await throttle(redis, request, config, 'school-timetable-' + str(user.id))
        key='lh:school-timetable:'+config.deployment+':'+str(user.id)+':'+identity.officer_id+':'+str(academic_year)+':'+str(semester)
        cached=await redis.get(key)
        if cached:return json.loads(cached)
        try:
            data=await teacher_timetable(identity.officer_id,identity.officer_code,academic_year,semester)
        except ValueError as error:
            if isinstance(error,DirectoryUnavailable):
                raise HTTPException(503, 'NRRU timetable is unavailable. Try again later.') from None
            raise HTTPException(400, 'Choose a supported year and semester') from None
        data['fetched_at']=datetime.now(timezone.utc).isoformat()
        await redis.set(key,json.dumps(data),ex=300)
        return data

@router.post('/search')
async def search(request:Request, response:Response, db:AsyncSession=Depends(get_db_session)):
    private(response)
    user, config, evidence = await context(request, db)
    boundary(request, config)
    hint = eligible(evidence)
    if not hint:
        raise HTTPException(403, 'Verified NRRU Google staff account required; sign in with Google again')
    async with resources(config) as (redis, _):
        await throttle(redis, request, config, 'school-directory-' + str(user.id))
        try:
            results = await search_directory(hint)
        except DirectoryUnavailable:
            raise HTTPException(503, 'NRRU directory is unavailable. Try again later.') from None
        search_id = secrets.token_urlsafe(32)
        payload = {'user_id':user.id, 'identity_id':evidence.identity_id,
            'email':evidence.email, 'observed_at':evidence.observed_at.isoformat(), 'candidates':results}
        await redis.set('lh:school:' + config.deployment + ':' + search_id, json.dumps(payload), ex=600)
    return {'search_id':search_id, 'search_hint':hint, 'candidates':results}

@router.post('/confirm')
async def confirm(body:Confirmation, request:Request, response:Response, db:AsyncSession=Depends(get_db_session)):
    private(response)
    user, config, evidence = await context(request, db)
    boundary(request, config)
    if not body.confirm_own_name or not eligible(evidence):
        raise HTTPException(403, 'Confirm your own directory name using verified NRRU Google access')
    async with resources(config) as (redis, _):
        await throttle(redis, request, config, 'school-confirm-' + str(user.id))
        key = 'lh:school:' + config.deployment + ':' + body.search_id
        raw = await redis.get(key)
        if not raw:
            raise HTTPException(409, 'Search expired. Search again.')
        payload = json.loads(raw)
        if (payload['user_id'] != user.id or payload['identity_id'] != evidence.identity_id
            or payload['email'] != evidence.email or payload['observed_at'] != evidence.observed_at.isoformat()):
            raise HTTPException(409, 'Google evidence changed. Search again.')
        selected = next((c for c in payload['candidates'] if c['officer_id'] == body.officer_id), None)
        if selected is None:
            raise HTTPException(409, 'Choose a result from your own search.')
        # Serialize same-user decisions; unique officer constraint closes cross-user races.
        from src.db.users import User
        await db.exec(select(User).where(User.id == user.id).with_for_update())
        await db.refresh(evidence)
        binding = await db.get(ProviderIdentity, evidence.identity_id)
        if (not eligible(evidence) or evidence.observed_at.isoformat() != payload['observed_at']
            or evidence.email != payload['email'] or binding is None or binding.retired_at is not None):
            raise HTTPException(409, 'Google evidence changed. Search again.')
        existing = await db.get(NrruTeacherIdentity, user.id)
        if existing is not None:
            if existing.officer_id != body.officer_id or existing.identity_id != evidence.identity_id:
                raise HTTPException(409, 'An existing association needs administrator review; it cannot be replaced here.')
            return {'confirmed':True}
        if await redis.eval(_CONSUME, 1, key, raw) != 1:
            raise HTTPException(409, 'Search already used. Search again.')
        db.add(NrruTeacherIdentity(user_id=user.id, identity_id=evidence.identity_id, **selected))
        db.add(UserAuditEvent(user_id=user.id, event_type='nrru_directory_self_confirmed',
            target_uuid=user.user_uuid, audit_metadata={'officer_id':body.officer_id,
            'source':'https://reg.nrru.ac.th/registrar/teach_time.asp',
            'confirmation':'self_attestation', 'role_grants':False, 'course_assignments':False}))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(409, 'This record already has an association. Ask an administrator to review.') from None
    return {'confirmed':True}
