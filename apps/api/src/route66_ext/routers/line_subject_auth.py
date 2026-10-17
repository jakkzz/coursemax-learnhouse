"""Explicit LINE linking, linked-only login, and server-verified LIFF handoff."""
from dataclasses import replace
import hashlib
import math
import time
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.route66_ext.adapters.core_events_database import get_db_session
from src.route66_ext.db.provider_identity import ProviderIdentity
from src.route66_ext.adapters.db_users import PublicUser, UserRead
from src.route66_ext.adapters.security_auth import decode_jwt, extract_jwt_from_request, get_current_user
from src.route66_ext.services.auth.line_config import line_settings
from src.route66_ext.services.auth.line_handoff import LineHandoffError, VerifiedLineHandoff, complete_line_handoff
from src.route66_ext.services.auth.native_line import complete_native_line, retire_line_identity
from src.route66_ext.services.auth.oauth_transactions import COOKIE_NAME, LinkActor, OAuthTransactionError
from src.route66_ext.services.auth.provider_identities import IdentityConflict, resolve_identity_owner
from src.route66_ext.services.auth.provider_proof import ProviderProofError, verify_line_liff_token, MAX_TOKEN_BYTES
from src.route66_ext.adapters.services_orgs_auth_policy import enforce_login_auth_method
from src.route66_ext.routers.google_subject_auth import boundary, resources, throttle

router=APIRouter()

class StartBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    intent: str=Field(pattern='^(signin|link)$')
    return_path: str=Field(default='/home',max_length=2000)

class CompleteBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    intent: str=Field(pattern='^(signin|link)$')
    state: str=Field(max_length=128,repr=False)
    code: str | None=Field(default=None,max_length=4096,repr=False)
    provider_error: str | None=Field(default=None,max_length=256)

class UnlinkBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    expected_identity_id: int=Field(gt=0)
    confirm_remove: bool

class LiffStartBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    return_path: str=Field(default='/home',max_length=2000)

class LiffBody(BaseModel):
    model_config=ConfigDict(extra='forbid')
    state: str=Field(max_length=128,repr=False)
    id_token: str=Field(repr=False)

async def recent_google_actor(request,db,config):
    user=await get_current_user(request,db)
    token=extract_jwt_from_request(request)
    payload=decode_jwt(token) if token else None
    authenticated_at=payload.get('lh_auth_time') if payload else None
    if (not isinstance(user,PublicUser) or not payload or payload.get('lhv')!=2
        or payload.get('amr')!='google' or payload.get('sorg')!=config.org_id
        or type(authenticated_at) not in (int,float) or not math.isfinite(authenticated_at)
        or not 0 <= time.time()-authenticated_at <= 300):
        raise HTTPException(401,'Sign in with Google again before managing LINE')
    return LinkActor(user.id,hashlib.sha256(token.encode()).hexdigest())

def session_response(request,response,user,session,return_path):
    response.headers['Cache-Control']='no-store'
    if session is None:
        return {'linked':True,'return_path':return_path}
    if session.mfa_required:
        return {'mfa_required':True,'mfa_token':session.mfa_token,'return_path':return_path}
    from src.route66_ext.adapters.routers_auth import set_auth_cookies, get_token_expiry_ms
    set_auth_cookies(response,session.access_token,session.refresh_token,request)
    return {'user':UserRead.model_validate(user),'return_path':return_path,
            'tokens':{'access_token':session.access_token,'refresh_token':session.refresh_token,
                      'expiry':get_token_expiry_ms()}}

@router.get('/capabilities')
async def capabilities(response:Response,db:AsyncSession=Depends(get_db_session)):
    response.headers['Cache-Control']='no-store'
    try:
        config=line_settings()
        await enforce_login_auth_method(db,config.org_id,'google')
    except HTTPException:
        return {'line':False,'link':False,'liff':False}
    allowed=True
    try:
        await enforce_login_auth_method(db,config.org_id,'line')
    except HTTPException:
        allowed=False
    return {'line':allowed,'link':True,'liff':allowed and config.liff_enabled}

@router.get('/account')
async def account(request:Request,response:Response,db:AsyncSession=Depends(get_db_session)):
    config=line_settings()
    user=await get_current_user(request,db)
    if not isinstance(user,PublicUser):raise HTTPException(401,'Sign in first')
    response.headers['Cache-Control']='private, no-store'
    row=(await db.exec(select(ProviderIdentity).where(ProviderIdentity.user_id==user.id,
        ProviderIdentity.provider=='line',ProviderIdentity.retired_at.is_(None)))).first()
    # Never disclose provider subject/channel identifiers to a public profile.
    try:
        await recent_google_actor(request,db,config)
        can_manage=True
    except HTTPException:
        can_manage=False
    return {'linked':row is not None,'identity_id':row.id if row else None,'can_manage':can_manage}

@router.post('/start')
async def start(request:Request,response:Response,body:StartBody,db:AsyncSession=Depends(get_db_session)):
    config=line_settings();boundary(request,config)
    actor=await recent_google_actor(request,db,config) if body.intent=='link' else None
    if body.intent=='signin':await enforce_login_auth_method(db,config.org_id,'line')
    async with resources(config) as (redis,transactions):
        await throttle(redis,request,config,'line-start')
        try:
            started=await transactions.begin(config.handoff.client,intent=body.intent,
                return_path=body.return_path,browser_cookie=request.cookies.get(COOKIE_NAME),actor=actor)
        except OAuthTransactionError:
            raise HTTPException(400,'Restart LINE sign-in') from None
    response.set_cookie(**started.binding_cookie());response.headers['Cache-Control']='no-store'
    return started.public_response()

@router.post('/complete')
async def complete(request:Request,response:Response,body:CompleteBody,db:AsyncSession=Depends(get_db_session)):
    config=line_settings();boundary(request,config)
    actor=await recent_google_actor(request,db,config) if body.intent=='link' else None
    try:
        async with resources(config) as (redis,transactions):
            await throttle(redis,request,config,'line-complete')
            async with httpx.AsyncClient(trust_env=False) as client:
                verified=await complete_line_handoff(transactions,config.handoff,state=body.state,
                    browser_cookie=request.cookies.get(COOKIE_NAME),intent=body.intent,actor=actor,
                    code=body.code,provider_error=body.provider_error,client=client)
        user,session=await complete_native_line(db,verified,org_id=config.org_id,
                                               namespace=config.handoff.client.provider_namespace)
        await db.commit()
    except (LineHandoffError,IdentityConflict,IntegrityError) as error:
        await db.rollback()
        raise HTTPException(409,str(error) if not isinstance(error,IntegrityError) else 'identity_conflict') from None
    except BaseException:
        await db.rollback();raise
    return session_response(request,response,user,session,verified.return_path)

@router.post('/unlink')
async def unlink(request:Request,response:Response,body:UnlinkBody,db:AsyncSession=Depends(get_db_session)):
    config=line_settings();boundary(request,config)
    actor=await recent_google_actor(request,db,config)
    if not body.confirm_remove:raise HTTPException(400,'Confirm removing LINE sign-in')
    async with resources(config) as (redis,_):await throttle(redis,request,config,'line-unlink')
    try:
        await retire_line_identity(db,actor_user_id=actor.user_id,expected_identity_id=body.expected_identity_id)
        await db.commit()
    except (IdentityConflict,IntegrityError):
        await db.rollback();raise HTTPException(409,'LINE connection changed; reload and review') from None
    except BaseException:
        await db.rollback();raise
    response.headers['Cache-Control']='no-store'
    return {'linked':False,'google_preserved':True}

@router.post('/liff/start')
async def liff_start(request:Request,response:Response,body:LiffStartBody|None=None,db:AsyncSession=Depends(get_db_session)):
    config=line_settings();boundary(request,config)
    if not config.liff_enabled:raise HTTPException(503,'LINE in-app access is not enabled')
    await enforce_login_auth_method(db,config.org_id,'line')
    # Different protocol/deployment guard: an OAuth state is not a LIFF challenge.
    liff_config=replace(config,deployment=config.deployment+'-liff')
    async with resources(liff_config) as (redis,transactions):
        await throttle(redis,request,liff_config,'liff-start')
        try:
            started=await transactions.begin(config.handoff.client,intent='signin',return_path=body.return_path if body else '/home',
                                              browser_cookie=request.cookies.get(COOKIE_NAME))
        except OAuthTransactionError:
            raise HTTPException(400,'Restart LINE sign-in') from None
    response.set_cookie(**started.binding_cookie());response.headers['Cache-Control']='no-store'
    return {'state':started.state,'liff_id':config.liff_id}

@router.post('/liff/session')
async def liff_session(request:Request,response:Response,body:LiffBody,db:AsyncSession=Depends(get_db_session)):
    config=line_settings();boundary(request,config)
    if not config.liff_enabled:raise HTTPException(503,'LINE in-app access is not enabled')
    if not 0 < len(body.id_token) <= MAX_TOKEN_BYTES:raise HTTPException(400,'Invalid LINE sign-in token')
    liff_config=replace(config,deployment=config.deployment+'-liff')
    try:
        async with resources(liff_config) as (redis,transactions):
            await throttle(redis,request,liff_config,'liff-session')
            transaction=await transactions.consume(config.handoff.client,intent='signin',state=body.state,
                                                    browser_cookie=request.cookies.get(COOKIE_NAME))
            async with httpx.AsyncClient(trust_env=False) as client:
                proof=await verify_line_liff_token(body.id_token,client_id=config.handoff.client.client_id,
                    provider_namespace=config.handoff.client.provider_namespace,client=client)
            owner=await resolve_identity_owner(db,proof)
            current=await get_current_user(request,db)
            if isinstance(current,PublicUser) and current.id!=owner:
                raise HTTPException(409,'Sign out before switching LINE accounts')
            existing=decode_jwt(extract_jwt_from_request(request) or '') or {}
            if isinstance(current,PublicUser) and existing.get('lhv')==2 and existing.get('amr')=='line':
                response.headers['Cache-Control']='no-store'
                return {'existing_session':True,'return_path':transaction.return_path}
            ttl=proof.expires_at-int(time.time()) if type(proof.expires_at) is int else 0
            if not 0 < ttl <= 604800:raise HTTPException(401,'Restart LINE sign-in')
            key='lh:liff:used:'+config.deployment+':'+hashlib.sha256(body.id_token.encode()).hexdigest()
            try:
                consumed=await redis.set(key,'1',nx=True,ex=ttl)
            except Exception:
                raise HTTPException(503,'LINE sign-in storage unavailable; try again') from None
            if not consumed:
                raise HTTPException(401,'LINE sign-in token was already used; sign in again')
        user,session=await complete_native_line(db,VerifiedLineHandoff(proof,'signin',transaction.return_path),
            org_id=config.org_id,namespace=config.handoff.client.provider_namespace)
        await db.commit()
    except (OAuthTransactionError,ProviderProofError,IdentityConflict,IntegrityError) as error:
        await db.rollback()
        code='line_link_required' if isinstance(error,IdentityConflict) and str(error)=='line_link_required' else 'line_signin_failed'
        raise HTTPException(409,{'code':code}) from None
    except BaseException:
        await db.rollback();raise
    return session_response(request,response,user,session,transaction.return_path)

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
