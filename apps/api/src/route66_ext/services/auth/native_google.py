"""Native Google ownership/admission integration; no email merges or notifications.

Caller owns the transaction. Registration requires verified handoff admission
(public mode or explicit allowlist) and a unique native email index; it never
invokes multi-commit signup helpers.
"""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, text
from sqlmodel import select

from src.route66_ext.adapters.db_organizations import Organization
from src.route66_ext.db.provider_identity import ProviderIdentity
from src.route66_ext.adapters.db_roles import Role, RoleTypeEnum
from src.route66_ext.adapters.db_user_organizations import UserOrganization
from src.route66_ext.adapters.db_users import User
from src.route66_ext.services.auth.provider_identities import link_existing_identity, resolve_identity_owner, IdentityConflict
from src.route66_ext.adapters.services_auth_session import issue_session_or_challenge
from src.route66_ext.adapters.services_orgs_auth_policy import enforce_login_auth_method


async def complete_native_google(db, verified, *, org_id):
    """Call only with server-verified handoff, in a transaction with no prior commit."""
    from src.route66_ext.services.academic_rosters import serialize, reconcile_login
    await serialize(db)  # Before user/identity locks; same order as roster imports.
    # Organization-first serializes staging admission and quota checks. All these
    # flows share this order, then user lock, then binding lock/unique constraints.
    org = (await db.exec(select(Organization).where(Organization.id == org_id).with_for_update())).first()
    if org is None:
        raise HTTPException(503, 'Google organization is not configured')
    await enforce_login_auth_method(db, org_id, 'google')
    proof = verified.proof
    if proof.provider != 'google' or not proof.verified_email:
        raise HTTPException(401, 'Invalid Google proof')
    intent = verified.intent
    if intent == 'continue':
        # Only the public-register handoff can produce this intent. Resolve
        # permanent subject ownership, never email, to select the native path.
        try:
            await resolve_identity_owner(db, proof)
        except IdentityConflict as error:
            if str(error) != 'google_registration_required':
                raise HTTPException(409, 'Google identity is unavailable') from error
            intent = 'register'
        else:
            intent = 'signin'
    if intent == 'link':
        if verified.actor is None:
            raise HTTPException(401, 'Sign in before linking Google')
        user = (await db.exec(select(User).where(User.id == verified.actor.user_id).with_for_update())).first()
        if user is None or not user.email_verified:
            raise HTTPException(403, 'A verified account is required to link Google')
        membership = (await db.exec(select(UserOrganization).where(
            UserOrganization.user_id == user.id, UserOrganization.org_id == org_id,
        ))).first()
        if membership is None:
            raise HTTPException(403, 'Organization access required')
        binding = await link_existing_identity(db, actor_user_id=user.id, proof=proof)
        # Explicit linking never mutates the native email, password, role or name.
    elif intent == 'signin':
        try:
            owner = await resolve_identity_owner(db, proof)
        except IdentityConflict as error:
            raise HTTPException(409, 'Google is not linked to an active account. Sign in using your existing method, then link Google.') from error
        user = (await db.exec(select(User).where(User.id == owner).with_for_update())).first()
        binding = (await db.exec(select(ProviderIdentity).where(
            ProviderIdentity.user_id == owner, ProviderIdentity.provider == 'google',
            ProviderIdentity.subject == proof.subject, ProviderIdentity.retired_at.is_(None),
        ).with_for_update())).first()
        if user is None or binding is None:
            raise HTTPException(409, 'Google identity changed. Restart sign-in.')
    elif intent == 'register':
        # Handoff admission verifies email and public/allowlist policy first.
        # Existing identities must choose signin, not create duplicates.
        try:
            await resolve_identity_owner(db, proof)
        except IdentityConflict as error:
            if str(error) != 'google_registration_required':
                raise HTTPException(409, 'Google identity is unavailable') from error
        else:
            raise HTTPException(409, 'This Google identity already has an account. Choose sign in.')
        if db.get_bind().dialect.name != 'postgresql':
            raise HTTPException(503, 'Registration requires validated PostgreSQL constraints')
        constraint = (await db.exec(text(
            "SELECT i.indisunique AND i.indisvalid AND i.indnkeyatts=1 "
            "AND i.indpred IS NULL AND i.indrelid='\"user\"'::regclass "
            "AND pg_get_indexdef(i.indexrelid,1,true) IN ('lower(email)', 'lower(email::text)', 'lower((email)::text)') "
            "FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname=current_schema() AND c.relname='uq_user_email_lower'"
        ))).first()
        if constraint is None or constraint[0] is not True:
            raise HTTPException(503, 'Registration is not ready')
        email = proof.verified_email.lower()
        collision = (await db.exec(select(User.id).where(func.lower(User.email) == email))).first()
        if collision is not None:
            raise HTTPException(409, 'An account already uses this email. Sign in using its existing method, then link Google.')
        role = await db.get(Role, 4)
        if role is None or role.org_id is not None or role.role_type != RoleTypeEnum.TYPE_GLOBAL:
            raise HTTPException(503, 'Learner role is not configured')
        rights = role.rights if isinstance(role.rights, dict) else role.rights.model_dump()
        if rights.get('dashboard', {}).get('action_access') or any(
            bucket.get(action) for name, bucket in rights.items() if isinstance(bucket, dict)
            for action in ('action_create', 'action_update', 'action_delete')
            # Native learners may start discussions. This is not authoring or
            # staff access; global discussion moderation remains prohibited.
            if not (name == 'discussions' and action == 'action_create')
        ):
            raise HTTPException(503, 'Learner role needs review')
        from src.route66_ext.adapters.security_features_utils_usage import check_limits_with_usage
        await check_limits_with_usage('members', org_id, db)
        created_at = datetime.now(timezone.utc)
        now = created_at.isoformat()
        user = User(username='learner_' + uuid4().hex, user_uuid='user_' + str(uuid4()),
                    first_name='', last_name='', email=email, password='', email_verified=True,
                    # Native email-subject sessions must predate neither this account nor its owner.
                    password_changed_at=created_at.replace(tzinfo=None),
                    email_verified_at=now, signup_method='google', creation_date=now, update_date=now)
        db.add(user)
        await db.flush()
        db.add(UserOrganization(user_id=user.id, org_id=org_id, role_id=4, creation_date=now, update_date=now))
        binding = await link_existing_identity(db, actor_user_id=user.id, proof=proof)
    else:
        raise HTTPException(400, 'Invalid Google intent')
    membership = (await db.exec(select(UserOrganization).where(
        UserOrganization.user_id == user.id, UserOrganization.org_id == org_id,
    ))).first()
    if membership is None:
        raise HTTPException(403, 'You are not a member of this organization')
    # Capture only server-verified Google evidence, never mutable profile email.
    # No backfill, domain-derived role, account merge or course assignment.
    from src.route66_ext.db.school_identity import SchoolGoogleEvidence
    evidence = await db.get(SchoolGoogleEvidence, binding.id)
    if evidence is None:
        evidence = SchoolGoogleEvidence(identity_id=binding.id, user_id=user.id,
            email=proof.verified_email.lower(), hosted_domain=proof.hosted_domain)
    else:
        evidence.email = proof.verified_email.lower()
        evidence.hosted_domain = proof.hosted_domain
        evidence.observed_at = datetime.now(timezone.utc)
    db.add(evidence)
    await db.flush()
    await reconcile_login(db, user.id)
    # Resolve the same stable subject through the native request guard before
    # minting; lifetime checks/MFA remain part of the one native session authority.
    from src.route66_ext.security.provider_session import claims, resolve_provider_session
    security = {**claims(user, binding.id), 'amr': 'google', 'sorg': org_id,
                'iat': datetime.now(timezone.utc).timestamp()}
    await resolve_provider_session(db, security)
    result = await issue_session_or_challenge(db, user, 'google', org_id, provider_identity_id=binding.id)
    return user, result

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
