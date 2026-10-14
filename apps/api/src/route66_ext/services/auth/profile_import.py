"""Best-effort, one-time Google profile enrichment; never identity or role changes.
Database state survives response/process failure. Retries occur on later verified
logins (max3), not an unauthenticated worker. Network I/O never holds user locks.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
import logging
import os
from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.route66_ext.db.provider_identity import ProviderIdentity
from src.route66_ext.db.provider_profile_import import ProviderProfileImport
from src.route66_ext.adapters.db_users import User
from src.route66_ext.services.users.provider_avatar import download_avatar, normalize_avatar

logger = logging.getLogger(__name__)
_slots = asyncio.Semaphore(2)

def enabled():
    return os.getenv('LEARNHOUSE_GOOGLE_PROFILE_IMPORT_ENABLED', 'false').lower() == 'true'

async def prepare_import(db, user, verified):
    if not enabled() or verified.proof.provider != 'google' or user.signup_method != 'google':
        return False  # Password-account linking is not implicit profile consent.
    row = await db.get(ProviderProfileImport, user.id)
    if row is not None:
        return row.status in ('pending','busy')
    profile = verified.proof.profile
    if profile is None:
        return False
    if not user.creation_date or user.update_date != user.creation_date:
        # Pre-feature edits have no per-field provenance. Do not infer that an
        # existing blank is permission to backfill a deliberately cleared name.
        db.add(ProviderProfileImport(user_id=user.id,status='skipped'))
        await db.flush()
        return False
    binding = (await db.exec(select(ProviderIdentity).where(
        ProviderIdentity.user_id == user.id, ProviderIdentity.provider == 'google',
        ProviderIdentity.subject == verified.proof.subject, ProviderIdentity.retired_at.is_(None),
    ))).first()
    if binding is None:
        return False
    # User is already locked by the governed Google controller. Fill once only.
    if not user.first_name and profile.given_name:
        user.first_name = profile.given_name
    if not user.last_name and profile.family_name:
        user.last_name = profile.family_name
    eligible = not user.avatar_image and bool(profile.picture)
    db.add(user)
    db.add(ProviderProfileImport(user_id=user.id, identity_id=binding.id,
        status='pending' if eligible else 'skipped', picture_url=profile.picture if eligible else None,
        display_name=profile.display_name, locale_hint=profile.locale))
    await db.flush()
    return eligible

async def cancel_import(db, user_id):
    if not enabled():
        return
    try:
        async with db.begin_nested():
            await _cancel_import(db, user_id)
    except Exception:
        logger.warning('Optional provider profile edit marker unavailable')

async def _cancel_import(db, user_id):
    row = (await db.exec(select(ProviderProfileImport).where(
        ProviderProfileImport.user_id == user_id).with_for_update())).first()
    if row is None:
        row = ProviderProfileImport(user_id=user_id, status='cancelled')
    else:
        row.status = 'cancelled'; row.picture_url = None; row.lease_until = None
    db.add(row)

async def stage_avatar(data, user_uuid):
    from src.route66_ext.adapters.config_config import get_learnhouse_config
    from src.route66_ext.adapters.security_file_validation import validate_upload
    from src.route66_ext.adapters.services_utils_upload_content import upload_content
    # Native filesystem storage is the deployed authority. S3 cleanup needs its
    # own acceptance before this optional importer can use it.
    if get_learnhouse_config().hosting_config.content_delivery.type != 'filesystem':
        raise ValueError('unsupported_storage')
    validate_upload(UploadFile(file=BytesIO(data), filename='provider-avatar.png'), ['image'], 2 * 1024 * 1024)
    filename = str(uuid4()) + '_provider_avatar.png'
    try:
        await upload_content(directory='avatars', type_of_dir='users', uuid=user_uuid,
            file_binary=data, file_and_format=filename, allowed_formats=['png'])
    except Exception:
        await remove_staged(user_uuid, filename)
        raise
    return filename

async def remove_staged(user_uuid, filename):
    from src.route66_ext.adapters.services_utils_upload_content import _safe_content_path
    if '/' in filename or '\\' in filename or '..' in filename:
        return
    path = Path(_safe_content_path('users', user_uuid, 'avatars', filename))
    await asyncio.to_thread(path.unlink, missing_ok=True)

async def import_avatar(user_id, *, sessions=None, downloader=download_avatar, stager=stage_avatar, remover=remove_staged):
    if not enabled():
        return
    if sessions is None:
        from src.route66_ext.adapters.core_events_database import engine
        from sqlalchemy.ext.asyncio import async_sessionmaker
        sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    staged = None; user_uuid = None; attached = False; lease = None
    try:
        async with _slots:
            async with sessions.begin() as db:
                user = (await db.exec(select(User).where(User.id == user_id).with_for_update())).first()
                row = (await db.exec(select(ProviderProfileImport).where(ProviderProfileImport.user_id == user_id).with_for_update())).first()
                now = datetime.now(timezone.utc)
                busy = row and row.status == 'busy' and row.lease_until and row.lease_until > now
                if not user or not row or busy or row.status not in ('pending','busy'):
                    return
                if row.attempts >= 3:
                    row.status='failed';row.picture_url=None;row.lease_until=None;db.add(row);return
                binding = await db.get(ProviderIdentity, row.identity_id)
                if user.avatar_image or not binding or binding.provider != 'google' or binding.user_id != user_id or binding.retired_at is not None:
                    row.status='skipped';row.picture_url=None;db.add(row);return
                url=row.picture_url;user_uuid=user.user_uuid
                lease=now + timedelta(seconds=90)
                row.status='busy';row.attempts+=1;row.lease_until=lease;db.add(row)
            data = await downloader('google', url)
            canonical = await asyncio.to_thread(normalize_avatar, data)
            staged = await stager(canonical, user_uuid)
            async with sessions.begin() as db:
                user = (await db.exec(select(User).where(User.id == user_id).with_for_update())).first()
                row = (await db.exec(select(ProviderProfileImport).where(ProviderProfileImport.user_id == user_id).with_for_update())).first()
                binding = await db.get(ProviderIdentity, row.identity_id) if row else None
                if (not user or not row or row.status != 'busy' or row.lease_until != lease or user.avatar_image
                    or not binding or binding.provider != 'google' or binding.user_id != user_id or binding.retired_at is not None):
                    return
                user.avatar_image=staged;row.status='complete';row.picture_url=None;row.lease_until=None
                db.add(user);db.add(row)
            attached=True
            from src.route66_ext.adapters.routers_users import _invalidate_session_cache
            _invalidate_session_cache(user_id)
    except Exception:
        # No exception text/URL/provider identifiers in logs; optional failure
        # must never rewrite a successful login response.
        logger.warning('Optional provider avatar import deferred')
        if lease is not None:
            try:
                async with sessions.begin() as db:
                    row = (await db.exec(select(ProviderProfileImport).where(ProviderProfileImport.user_id == user_id).with_for_update())).first()
                    if row and row.status == 'busy' and row.lease_until == lease:
                        row.status='failed' if row.attempts >= 3 else 'pending';row.lease_until=None
                        if row.status=='failed':row.picture_url=None
                        db.add(row)
            except Exception:
                logger.warning('Optional provider avatar retry state unavailable')
    finally:
        if staged and not attached:
            try:
                # A failed commit can have an ambiguous outcome. Never remove
                # an object unless a fresh, locked read proves it unattached.
                async with sessions.begin() as db:
                    user=(await db.exec(select(User).where(User.id==user_id).with_for_update())).first()
                    if not user or user.avatar_image != staged:
                        await remover(user_uuid, staged)
            except Exception:
                logger.warning('Optional staged avatar cleanup deferred')

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
