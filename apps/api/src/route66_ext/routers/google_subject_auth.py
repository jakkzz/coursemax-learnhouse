"""Server-owned Google flow; exact origin, native sessions, explicit admission."""
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
import hashlib
import json
import os
import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from src.route66_ext.adapters.config_config import get_learnhouse_config
from src.route66_ext.adapters.core_events_database import get_db_session
from src.route66_ext.adapters.security_auth import get_current_user, extract_jwt_from_request
from src.route66_ext.adapters.db_users import PublicUser, UserRead, User
from src.route66_ext.services.auth.google_handoff import GoogleHandoffConfig, GoogleHandoffError, complete_google_handoff
from src.route66_ext.services.auth.oauth_transactions import OAuthClient, OAuthTransactions, RedisTransactionStore, LinkActor, COOKIE_NAME
from src.route66_ext.services.auth.native_google import complete_native_google
from src.route66_ext.services.auth.provider_identities import IdentityConflict
from src.route66_ext.adapters.services_orgs_auth_policy import enforce_login_auth_method
from src.route66_ext.adapters.services_security_rate_limiting import get_client_ip

router = APIRouter()
_LIMIT = "local n=redis.call('INCR',KEYS[1]); if n==1 then redis.call('EXPIRE',KEYS[1],300) end; return n"


@dataclass(frozen=True)
class Settings:
    handoff: GoogleHandoffConfig
    org_id: int
    deployment: str
    secret: bytes = field(repr=False)


def settings():
    if os.getenv('LEARNHOUSE_GOOGLE_SUBJECT_LOGIN_ENABLED', 'false').lower() != 'true':
        raise HTTPException(503, 'Google sign-in is not enabled')
    try:
        config = get_learnhouse_config()
        if not config.hosting_config.ssl:
            raise ValueError()
        client = OAuthClient('google', os.environ['GOOGLE_CLIENT_ID'],
                             'https://' + config.hosting_config.domain, 'global')
        allowed = json.loads(os.getenv('LEARNHOUSE_GOOGLE_REGISTRATION_EMAILS', '[]'))
        if not isinstance(allowed, list) or not all(isinstance(x, str) for x in allowed):
            raise ValueError()
        handoff = GoogleHandoffConfig(client, os.environ['GOOGLE_CLIENT_SECRET'], frozenset(allowed),
            public_registration=os.getenv('LEARNHOUSE_GOOGLE_PUBLIC_REGISTRATION_ENABLED', 'false').lower() == 'true')
        org_id = int(os.environ['LEARNHOUSE_GOOGLE_ORG_ID'])
        secret = os.environ['LEARNHOUSE_OAUTH_TRANSACTION_SECRET'].encode()
        deployment = os.environ['LEARNHOUSE_OAUTH_DEPLOYMENT']
        if org_id <= 0 or len(secret) < 32:
            raise ValueError()
        return Settings(handoff, org_id, deployment, secret)
    except (ValueError, KeyError, TypeError):
        raise HTTPException(503, 'Google sign-in configuration needs review') from None


def boundary(request, config):
    if request.headers.get('origin') != config.handoff.client.public_origin:
        raise HTTPException(403, 'Restart sign-in from this site')
    # Reject duplicate security cookies BEFORE Starlette/Next choose one value.
    names = [part.strip().partition('=')[0] for part in request.headers.get('cookie', '').split(';')]
    for name in (COOKIE_NAME, 'LH_access', 'LH_refresh'):
        if names.count(name) > 1:
            raise HTTPException(400, 'Ambiguous sign-in cookies. Clear this site cookies and retry.')


@asynccontextmanager
async def resources(config):
    connection = get_learnhouse_config().redis_config.redis_connection_string
    if not connection:
        raise HTTPException(503, 'Sign-in storage unavailable')
    redis = Redis.from_url(connection, socket_timeout=3, socket_connect_timeout=3)
    try:
        transactions = OAuthTransactions(RedisTransactionStore(redis), deployment=config.deployment, secret=config.secret)
        yield redis, transactions
    finally:
        await redis.aclose()


async def throttle(redis, request, config, action, *, limit=30):
    key = 'lh:oauth-rate:' + config.deployment + ':' + action + ':' + hashlib.sha256(get_client_ip(request).encode()).hexdigest()
    try:
        count = await redis.eval(_LIMIT, 1, key)
    except Exception:
        raise HTTPException(503, 'Sign-in storage unavailable') from None
    if count > limit:
        raise HTTPException(429, 'Too many sign-in attempts. Wait five minutes.', headers={'Retry-After': '300'})


async def actor_for(request, db, intent):
    if intent != 'link':
        return None
    user = await get_current_user(request, db)
    token = extract_jwt_from_request(request)
    if not isinstance(user, PublicUser) or not token:
        raise HTTPException(401, 'Sign in before linking Google')
    return LinkActor(user.id, hashlib.sha256(token.encode()).hexdigest())


class StartBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    intent: str = Field(pattern='^(signin|register|link)$')
    return_path: str = Field(default='/home', max_length=2000)
    current_password: str | None = Field(default=None, max_length=1024, repr=False)


class CompleteBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    intent: str = Field(pattern='^(signin|register|link)$')
    state: str = Field(max_length=128)
    code: str | None = Field(default=None, max_length=4096)
    provider_error: str | None = Field(default=None, max_length=256)


@router.get('/capabilities')
async def capabilities(db: AsyncSession = Depends(get_db_session)):
    try:
        config = settings()
        await enforce_login_auth_method(db, config.org_id, 'google')
    except HTTPException:
        return {'google': False, 'registration': False, 'public_registration': False}
    return {'google': True, 'registration': config.handoff.registration_enabled,
            'public_registration': config.handoff.public_registration}


@router.get('/account')
async def account(request: Request, response: Response, db: AsyncSession = Depends(get_db_session)):
    """Private, read-only connection status; never expose a provider subject."""
    from sqlmodel import select
    from src.route66_ext.db.provider_identity import ProviderIdentity

    private_headers = {'Cache-Control': 'private, no-store', 'Vary': 'Cookie, Authorization'}
    user = await get_current_user(request, db)
    if not isinstance(user, PublicUser):
        raise HTTPException(401, 'Sign in first', headers=private_headers)
    response.headers.update(private_headers)
    identity_id = (await db.exec(select(ProviderIdentity.id).where(
        ProviderIdentity.user_id == user.id,
        ProviderIdentity.provider == 'google',
        ProviderIdentity.issuer == 'https://accounts.google.com',
        ProviderIdentity.namespace == 'global',
        ProviderIdentity.retired_at.is_(None),
    ))).first()
    return {'linked': identity_id is not None}


@router.post('/start')
async def start(request: Request, response: Response, body: StartBody, db: AsyncSession = Depends(get_db_session)):
    config = settings()
    boundary(request, config)
    await enforce_login_auth_method(db, config.org_id, 'google')
    if body.intent == 'register' and not config.handoff.registration_enabled:
        raise HTTPException(403, 'Registration is by invitation during staging')
    async with resources(config) as (redis, transactions):
        await throttle(redis, request, config, 'start')
        actor = await actor_for(request, db, body.intent)
        if actor is not None:
            from src.route66_ext.adapters.security_auth import decode_jwt
            from src.route66_ext.adapters.services_users_users import security_verify_password
            payload = decode_jwt(extract_jwt_from_request(request)) or {}
            if payload.get('lhv') != 2:
                user = await db.get(User, actor.user_id)
                try:
                    valid = bool(user and user.password and body.current_password and security_verify_password(body.current_password, user.password))
                except Exception:
                    valid = False
                if not valid:
                    raise HTTPException(401, 'Confirm your password before linking Google')
        from src.route66_ext.services.auth.oauth_transactions import OAuthTransactionError
        try:
            started = await transactions.begin(config.handoff.client, intent=body.intent,
                return_path=body.return_path, browser_cookie=request.cookies.get(COOKIE_NAME), actor=actor)
        except OAuthTransactionError:
            raise HTTPException(400, 'Restart Google sign-in') from None
    response.set_cookie(**started.binding_cookie())
    response.headers['Cache-Control'] = 'no-store'
    return started.public_response()


@router.post('/complete')
async def complete(request: Request, response: Response, body: CompleteBody, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db_session)):
    config = settings()
    profile_queued = False
    boundary(request, config)
    actor = await actor_for(request, db, body.intent)
    try:
        async with resources(config) as (redis, transactions):
            await throttle(redis, request, config, 'complete')
            async with httpx.AsyncClient(trust_env=False) as http:
                verified = await complete_google_handoff(transactions, config.handoff,
                    state=body.state, browser_cookie=request.cookies.get(COOKIE_NAME),
                    intent=body.intent, code=body.code, provider_error=body.provider_error,
                    actor=actor, client=http)
        user, session = await complete_native_google(db, verified, org_id=config.org_id)
        if not session.mfa_required:
            from src.route66_ext.services.auth.profile_import import enabled, prepare_import
            if enabled():
                try:
                    async with db.begin_nested():
                        profile_queued = await prepare_import(db, user, verified)
                except Exception:
                    logging.getLogger(__name__).warning('Optional provider profile import unavailable')
                    await db.refresh(user)
        await db.commit()
    except (GoogleHandoffError, IdentityConflict, IntegrityError) as error:
        await db.rollback()
        detail = str(error) if isinstance(error, (GoogleHandoffError, IdentityConflict)) else 'account_conflict'
        raise HTTPException(409, detail) from None
    except BaseException:
        await db.rollback()
        raise
    if profile_queued:
        from src.route66_ext.services.auth.profile_import import import_avatar
        background_tasks.add_task(import_avatar, user.id)
    response.headers['Cache-Control'] = 'no-store'
    # Keep shared binding cookie until TTL for concurrent tabs; state is single-use.
    if session.mfa_required:
        return {'mfa_required': True, 'mfa_token': session.mfa_token, 'return_path': verified.return_path}
    from src.route66_ext.adapters.routers_auth import set_auth_cookies, get_token_expiry_ms
    set_auth_cookies(response, session.access_token, session.refresh_token, request)
    return {'user': UserRead.model_validate(user), 'return_path': verified.return_path,
            'tokens': {'access_token': session.access_token, 'refresh_token': session.refresh_token,
                       'expiry': get_token_expiry_ms()}}

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
