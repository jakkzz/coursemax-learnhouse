"""Google sessions use native JWT/cookies/MFA with immutable account subjects.

Legacy password sessions remain compatible. Google never uses email as a subject.
Provider sessions fail closed if their owner/binding/org or revocation store changes.
"""
from datetime import datetime, timezone
import re
import math
import os

from fastapi import HTTPException
from sqlmodel import select

from src.route66_ext.adapters.config_config import get_learnhouse_config
from src.route66_ext.db.provider_identity import ProviderIdentity
from src.route66_ext.adapters.db_user_organizations import UserOrganization
from src.route66_ext.adapters.db_users import User

VERSION = 'lhv'
BINDING = 'lh_identity'
AUDIENCE = 'learnhouse-native-session'
_SUBJECT = re.compile(r'lh:user:([1-9][0-9]*)')


def issuer():
    hosting = get_learnhouse_config().hosting_config
    return ('https://' if hosting.ssl else 'http://') + hosting.domain


def claims(user, identity_id, *, auth_time=None):
    if type(user.id) is not int or type(identity_id) is not int or not user.user_uuid:
        raise ValueError('invalid_session_identity')
    return {VERSION: 2, 'sub': f'lh:user:{user.id}', 'lh_uuid': user.user_uuid,
            BINDING: identity_id, 'iss': issuer(), 'aud': AUDIENCE,
            'lh_auth_time': datetime.now(timezone.utc).timestamp() if auth_time is None else auth_time}


def validate_claims(payload):
    return (
        payload.get(VERSION) == 2 and type(payload.get(VERSION)) is int
        and isinstance(payload.get('sub'), str) and _SUBJECT.fullmatch(payload['sub']) is not None
        and isinstance(payload.get('lh_uuid'), str) and bool(payload['lh_uuid'])
        and type(payload.get(BINDING)) is int and payload[BINDING] > 0
        and payload.get('iss') == issuer() and payload.get('aud') == AUDIENCE
        and payload.get('amr') in ('google', 'line') and type(payload.get('sorg')) is int
        and type(payload.get('iat')) in (int, float)
    )


def carried_claims(payload):
    return {key: payload[key] for key in (VERSION, BINDING, 'lh_uuid', 'iss', 'aud', 'lh_auth_time') if key in payload}


async def resolve_provider_session(db, payload, *, check_revocation=True):
    if not validate_claims(payload):
        raise HTTPException(401, 'Invalid provider session')
    ident = int(_SUBJECT.fullmatch(payload['sub'])[1])
    user = (await db.exec(select(User).where(User.id == ident))).first()
    binding = (await db.exec(select(ProviderIdentity).where(ProviderIdentity.id == payload[BINDING]))).first()
    if (
        user is None or user.user_uuid != payload['lh_uuid'] or not user.email_verified
        or binding is None or binding.user_id != ident or binding.provider != payload.get('amr')
        or binding.retired_at is not None
    ):
        raise HTTPException(401, 'Provider session is no longer active')
    if payload['amr'] == 'line':
        if (os.getenv('LEARNHOUSE_LINE_SUBJECT_LOGIN_ENABLED', 'false').lower() != 'true'
            or binding.namespace != os.getenv('LEARNHOUSE_LINE_PROVIDER_ID')
            or binding.issuer != 'https://access.line.me'):
            raise HTTPException(401, 'LINE sign-in is no longer available')
        google = (await db.exec(select(ProviderIdentity.id).where(
            ProviderIdentity.user_id == ident, ProviderIdentity.provider == 'google',
            ProviderIdentity.retired_at.is_(None),
        ))).first()
        if google is None:
            raise HTTPException(401, 'Google account recovery is required')
    now = datetime.now(timezone.utc)
    if user.locked_until:
        try:
            until = datetime.fromisoformat(user.locked_until)
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            if until > now:
                raise HTTPException(401, 'Account is locked')
        except ValueError:
            raise HTTPException(401, 'Account is locked') from None
    if user.password_changed_at:
        cutoff = user.password_changed_at
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        if payload['iat'] < cutoff.timestamp():
            raise HTTPException(401, 'Session revoked')
    membership = (await db.exec(select(UserOrganization).where(
        UserOrganization.user_id == ident, UserOrganization.org_id == payload['sorg'],
    ))).first()
    if membership is None:
        raise HTTPException(403, 'Organization access removed')
    from src.route66_ext.adapters.services_orgs_auth_policy import enforce_login_auth_method
    await enforce_login_auth_method(db, payload['sorg'], payload['amr'])
    if check_revocation:
        # Do not use native fail-open revocation helpers for provider sessions.
        from src.route66_ext.adapters.core_redis import get_redis_client
        try:
            redis = get_redis_client()
            if redis is None:
                raise RuntimeError()
            cutoff = redis.get(f'jwt_revoked_before:{ident}')
            if cutoff is not None:
                cutoff = float(cutoff)
                if not math.isfinite(cutoff):
                    raise ValueError('Invalid session cutoff')
                if payload['iat'] <= cutoff:
                    raise HTTPException(401, 'Session revoked')
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, 'Session validation temporarily unavailable') from None
    return user


def mfa_challenge_usable(payload):
    """Refuse a spent provider challenge before consuming a backup code."""
    jti = payload.get('jti')
    if payload.get('purpose') != 'mfa_pending' or not isinstance(jti, str) or re.fullmatch(r'[A-Za-z0-9_-]{43}', jti) is None:
        return False
    from src.route66_ext.adapters.core_redis import get_redis_client
    try:
        redis = get_redis_client()
        if redis is None:
            raise RuntimeError()
        return redis.get(f'lh:mfa:used:{jti}') is None
    except Exception:
        raise HTTPException(503, 'Session validation temporarily unavailable') from None


def consume_mfa_challenge(payload):
    """Claim a successfully verified provider challenge once, fail closed."""
    jti = payload.get('jti')
    if payload.get('purpose') != 'mfa_pending' or not isinstance(jti, str) or re.fullmatch(r'[A-Za-z0-9_-]{43}', jti) is None:
        raise HTTPException(401, 'Please restart sign-in')
    from src.route66_ext.adapters.core_redis import get_redis_client
    try:
        redis = get_redis_client()
        if redis is None:
            raise RuntimeError()
        claimed = redis.set(f'lh:mfa:used:{jti}', '1', nx=True, ex=300)
    except Exception:
        raise HTTPException(503, 'Session validation temporarily unavailable') from None
    if not claimed:
        raise HTTPException(401, 'Please restart sign-in')

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
