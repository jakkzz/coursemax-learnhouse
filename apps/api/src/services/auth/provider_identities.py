"""Transactional subject ownership, NOT session authorization.

No route imports this service yet. A controller must consume OAuth transactions,
verify provider proof, authenticate/re-authenticate the native actor, and check
account lifecycle/MFA/org policy. Replacement must also invalidate affected native
sessions before its API is enabled; retiring a subject alone does not revoke JWTs.
Proof and actor IDs must never come from raw
browser assertions. Resolution alone is not permission to mint a session.

There is no user creation, email lookup/change, merge, generic unlink or commit in
this module. The caller owns the outer transaction; savepoints protect against
partial retirement even if the caller catches a failed replacement and commits.
"""
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.provider_identity import ProviderIdentity, ProviderIdentityEvent
from src.db.users import User
from src.services.auth.provider_proof import ProviderProof


class IdentityConflict(ValueError):
    """Stable redacted error code, with no subject/email/token details."""


def _key(proof: ProviderProof) -> tuple[str, str, str, str]:
    if not isinstance(proof, ProviderProof):
        raise IdentityConflict("invalid_provider_proof")
    values = (proof.provider, proof.issuer, proof.namespace, proof.subject)
    for value, maximum in zip(values, (16, 128, 128, 255)):
        if not isinstance(value, str) or not 0 < len(value) <= maximum or not value.isascii() or not value.isprintable() or value != value.strip():
            raise IdentityConflict("invalid_provider_proof")
    if proof.provider == "google":
        if proof.issuer != "https://accounts.google.com" or proof.namespace != "global" or not isinstance(proof.verified_email, str) or not proof.verified_email.strip():
            raise IdentityConflict("invalid_provider_proof")
    elif proof.provider != "line" or proof.issuer != "https://access.line.me":
        raise IdentityConflict("invalid_provider_proof")
    return values


async def _find(db: AsyncSession, proof: ProviderProof) -> ProviderIdentity | None:
    provider, issuer, namespace, subject = _key(proof)
    query = select(ProviderIdentity).where(
        ProviderIdentity.provider == provider, ProviderIdentity.issuer == issuer,
        ProviderIdentity.namespace == namespace, ProviderIdentity.subject == subject,
    ).execution_options(populate_existing=True)
    return (await db.exec(query)).first()


async def _user_lock(db: AsyncSession, actor_user_id: int) -> User:
    if type(actor_user_id) is not int or actor_user_id <= 0:
        raise IdentityConflict("invalid_actor")
    user = (await db.exec(select(User).where(User.id == actor_user_id).with_for_update().execution_options(populate_existing=True))).first()
    if user is None:
        raise IdentityConflict("account_not_found")
    return user


async def _active(db: AsyncSession, user_id: int, provider: str) -> ProviderIdentity | None:
    return (await db.exec(select(ProviderIdentity).where(
        ProviderIdentity.user_id == user_id, ProviderIdentity.provider == provider,
        ProviderIdentity.retired_at.is_(None),
    ).execution_options(populate_existing=True))).first()


def _assert_owner(binding: ProviderIdentity, user_id: int) -> None:
    if binding.retired_at is not None:
        raise IdentityConflict("identity_retired")
    if binding.user_id != user_id:
        raise IdentityConflict("identity_already_owned")


async def resolve_identity_owner(db: AsyncSession, proof: ProviderProof) -> int:
    """Resolve ownership only. Unknown LINE never creates an account.

    The caller must recheck lifecycle and binding validity in its session-issuance
    transaction; this read does not lock an identity against later replacement.
    """
    binding = await _find(db, proof)
    if binding is None:
        raise IdentityConflict("line_link_required" if proof.provider == "line" else "google_registration_required")
    if binding.retired_at is not None:
        raise IdentityConflict("identity_retired")
    return binding.user_id


async def _bind(db: AsyncSession, user_id: int, proof: ProviderProof, reason: str) -> ProviderIdentity:
    existing = await _find(db, proof)
    if existing is not None:
        _assert_owner(existing, user_id)
        return existing
    if await _active(db, user_id, proof.provider) is not None:
        raise IdentityConflict("provider_already_linked")
    provider, issuer, namespace, subject = _key(proof)
    result = await db.exec(insert(ProviderIdentity).values(
        user_id=user_id, provider=provider, issuer=issuer, namespace=namespace,
        subject=subject, created_at=datetime.now(timezone.utc),
    ).on_conflict_do_nothing(constraint="uq_provider_identity_subject").returning(ProviderIdentity.id))
    identity_id = result.scalar_one_or_none()
    if identity_id is None:
        # Another user's transaction may have won the unique-subject race. Under
        # PostgreSQL READ COMMITTED, this new statement sees its committed row.
        existing = await _find(db, proof)
        if existing is None:
            raise IdentityConflict("identity_conflict_retry")
        _assert_owner(existing, user_id)
        return existing
    db.add(ProviderIdentityEvent(identity_id=identity_id, actor_user_id=user_id, kind="bound", reason=reason))
    await db.flush()
    return await db.get(ProviderIdentity, identity_id)


async def link_existing_identity(db: AsyncSession, *, actor_user_id: int, proof: ProviderProof) -> ProviderIdentity:
    _key(proof)
    async with db.begin_nested():
        user = await _user_lock(db, actor_user_id)
        if proof.provider == "line" and (
            not user.email_verified or await _active(db, actor_user_id, "google") is None
        ):
            raise IdentityConflict("verified_google_link_required")
        return await _bind(db, actor_user_id, proof, "explicit_link")


async def replace_google_identity(
    db: AsyncSession, *, actor_user_id: int, expected_identity_id: int,
    current_proof: ProviderProof, new_proof: ProviderProof, reason: str,
) -> ProviderIdentity:
    """Both proofs must be recently verified, with distinct consumed transactions.

    This is not lost-account recovery. A stale expected identity is a safe conflict,
    not permission to overwrite whichever Google identity is currently active.
    """
    old_key, new_key = _key(current_proof), _key(new_proof)
    if current_proof.provider != "google" or new_proof.provider != "google":
        raise IdentityConflict("google_proof_required")
    if type(expected_identity_id) is not int or expected_identity_id <= 0:
        raise IdentityConflict("invalid_expected_identity")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise IdentityConflict("replacement_reason_required")
    async with db.begin_nested():
        await _user_lock(db, actor_user_id)
        old = await _active(db, actor_user_id, "google")
        if old is None or old.id != expected_identity_id:
            raise IdentityConflict("identity_changed")
        if (old.provider, old.issuer, old.namespace, old.subject) != old_key:
            raise IdentityConflict("current_identity_proof_required")
        if old_key == new_key:
            return old
        other = await _find(db, new_proof)
        if other is not None:
            _assert_owner(other, actor_user_id)
            raise IdentityConflict("identity_conflict_retry")
        old.retired_at = datetime.now(timezone.utc)
        old.retirement_reason = reason.strip()
        db.add(old)
        db.add(ProviderIdentityEvent(identity_id=old.id, actor_user_id=actor_user_id, kind="retired", reason=reason.strip()))
        await db.flush()
        return await _bind(db, actor_user_id, new_proof, "google_replacement")
