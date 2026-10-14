"""Google-owned LINE linking/linked-only native sessions; never user creation."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlmodel import select
from src.route66_ext.db.provider_identity import ProviderIdentityEvent
from src.route66_ext.adapters.db_user_organizations import UserOrganization
from src.route66_ext.services.auth.provider_identities import IdentityConflict, _key, _find, _active, _user_lock, link_existing_identity
from src.route66_ext.adapters.services_auth_session import issue_session_or_challenge
from src.route66_ext.adapters.services_orgs_auth_policy import enforce_login_auth_method

async def complete_native_line(db, verified, *, org_id, namespace):
    proof = verified.proof
    _key(proof)
    if proof.provider != 'line' or proof.namespace != namespace:
        raise IdentityConflict('invalid_line_proof')
    if verified.intent == 'link':
        if verified.actor is None:
            raise IdentityConflict('verified_google_link_required')
        user = await _user_lock(db, verified.actor.user_id)
        # Native actor lifecycle was verified at both start and callback. Never
        # turn a linking action into a LINE sign-in or switch its browser account.
        await link_existing_identity(db, actor_user_id=user.id, proof=proof)
        return user, None
    if verified.intent != 'signin' or verified.actor is not None:
        raise IdentityConflict('invalid_line_intent')
    binding = await _find(db, proof)
    if binding is None:
        raise IdentityConflict('line_link_required')
    user = await _user_lock(db, binding.user_id)
    binding = await _find(db, proof)
    if binding is None or binding.retired_at is not None or binding.user_id != user.id:
        raise IdentityConflict('identity_retired')
    if not user.email_verified or await _active(db, user.id, 'google') is None:
        raise IdentityConflict('verified_google_link_required')
    membership = (await db.exec(select(UserOrganization).where(
        UserOrganization.user_id == user.id, UserOrganization.org_id == org_id,
    ))).first()
    if membership is None:
        raise HTTPException(403, 'You are not a member of this organization')
    await enforce_login_auth_method(db, org_id, 'line')
    # Apply the same strict binding/account/lock/revocation guard before minting.
    from src.route66_ext.security.provider_session import claims, resolve_provider_session
    payload = {**claims(user, binding.id), 'amr': 'line', 'sorg': org_id,
               'iat': datetime.now(timezone.utc).timestamp()}
    await resolve_provider_session(db, payload)
    return user, await issue_session_or_challenge(db, user, 'line', org_id,
                                                 provider_identity_id=binding.id)

async def retire_line_identity(db, *, actor_user_id, expected_identity_id):
    """Controller requires recent verified Google session and explicit confirmation.

    Retain the permanent reservation. A removed subject cannot be casually linked
    again, to this account or another; recovery is a separately reviewed workflow.
    Existing LINE access/refresh/MFA immediately fail the active-binding guard.
    """
    async with db.begin_nested():
        user = await _user_lock(db, actor_user_id)
        if not user.email_verified or await _active(db, user.id, 'google') is None:
            raise IdentityConflict('verified_google_link_required')
        line = await _active(db, user.id, 'line')
        if line is None or type(expected_identity_id) is not int or line.id != expected_identity_id:
            raise IdentityConflict('identity_changed')
        line.retired_at = datetime.now(timezone.utc)
        line.retirement_reason = 'explicit_line_unlink'
        db.add(line)
        db.add(ProviderIdentityEvent(identity_id=line.id, actor_user_id=user.id,
                                     kind='retired', reason='explicit_line_unlink'))
        await db.flush()

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
