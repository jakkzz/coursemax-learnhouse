"""Opt-in PostgreSQL tests; only the disposable harness's Unix socket is used."""
import asyncio
from dataclasses import replace
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.users import User
from src.route66_ext.db.provider_identity import ProviderIdentity, ProviderIdentityEvent, GUARD_DDL, EVENT_GUARD_DDL
from src.route66_ext.services.auth.provider_proof import ProviderProof
from src.route66_ext.services.auth.provider_identities import IdentityConflict, link_existing_identity, replace_google_identity, resolve_identity_owner

SPEC = importlib.util.spec_from_file_location("identity_migration", Path("migrations/versions/c71a02d9ef40_provider_identity_ownership.py"))
MIGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MIGRATION)


def migrate(connection, direction="upgrade"):
    with Operations.context(MigrationContext.configure(connection)):
        getattr(MIGRATION, direction)()


@unittest.skipUnless(os.getenv("RUN_IDENTITY_POSTGRES_TESTS") == "1", "requires isolated PostgreSQL fixture")
class ProviderIdentityPostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if os.environ.get("IDENTITY_TEST_PG_SOCKET") != "/scratch":
            raise RuntimeError("Use the dedicated Unix-socket harness")
        self.schema = "identity_test_" + uuid.uuid4().hex
        url = "postgresql+asyncpg://fixture@/fixture"
        self.admin = create_async_engine(url, connect_args={"host": "/scratch"})
        async with self.admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.engine = create_async_engine(url, connect_args={"host": "/scratch", "server_settings": {"search_path": self.schema}}, isolation_level="READ COMMITTED")
        async with self.engine.begin() as conn:
            await conn.run_sync(User.__table__.create)
            await conn.run_sync(migrate)
        self.sessions = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        async with self.sessions.begin() as db:
            for ident in (1, 2, 3):
                db.add(User(id=ident, username=f"fixture{ident}", first_name="Synthetic", last_name="Fixture",
                            email=f"fixture{ident}@example.com", email_verified=(ident != 3), user_uuid=f"user_fixture_{ident}"))
        self.google = ProviderProof("google", "https://accounts.google.com", "global", "google-subject", "verified@example.com")
        self.line = ProviderProof("line", "https://access.line.me", "reviewed-provider", "line-subject")

    async def asyncTearDown(self):
        await self.engine.dispose()
        async with self.admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
        await self.admin.dispose()

    async def link(self, user=1, proof=None):
        async with self.sessions.begin() as db:
            result = await link_existing_identity(db, actor_user_id=user, proof=proof or self.google)
            return result.id

    async def counts(self):
        async with self.sessions() as db:
            return (await db.exec(text('SELECT (SELECT count(*) FROM provideridentity), (SELECT count(*) FROM provideridentityevent), (SELECT count(*) FROM "user")'))).one()

    async def test_binding_is_idempotent_and_does_not_use_or_change_email(self):
        identity = await self.link()
        same_subject = replace(self.google, verified_email="changed@example.com")
        self.assertEqual(await self.link(proof=same_subject), identity)
        async with self.sessions() as db:
            self.assertEqual(await resolve_identity_owner(db, same_subject), 1)
            self.assertEqual((await db.get(User, 1)).email, "fixture1@example.com")
        self.assertEqual(tuple(await self.counts()), (1, 1, 3))

    async def test_same_email_different_subject_never_matches_existing_owner(self):
        await self.link()
        unknown = replace(self.google, subject="different-subject")
        async with self.sessions() as db:
            with self.assertRaisesRegex(IdentityConflict, "google_registration_required"):
                await resolve_identity_owner(db, unknown)
        self.assertEqual(tuple(await self.counts()), (1, 1, 3))

    async def test_unknown_line_cannot_create_account(self):
        async with self.sessions() as db:
            with self.assertRaisesRegex(IdentityConflict, "line_link_required"):
                await resolve_identity_owner(db, self.line)
        self.assertEqual(tuple(await self.counts()), (0, 0, 3))

    async def test_line_link_requires_verified_native_email_and_active_google(self):
        with self.assertRaisesRegex(IdentityConflict, "verified_google_link_required"):
            await self.link(proof=self.line)
        await self.link(user=3)
        with self.assertRaisesRegex(IdentityConflict, "verified_google_link_required"):
            await self.link(user=3, proof=self.line)
        await self.link(proof=replace(self.google, subject="another-google"))
        await self.link(proof=self.line)
        async with self.sessions() as db:
            self.assertEqual(await resolve_identity_owner(db, self.line), 1)

    async def test_invalid_actor_or_proof_never_writes(self):
        for actor, proof in [(0, self.google), (True, self.google), (999, self.google),
                             (1, replace(self.google, verified_email=None)),
                             (1, replace(self.google, namespace="wrong")),
                             (1, replace(self.google, issuer="https://attacker.example"))]:
            async with self.sessions.begin() as db:
                with self.assertRaises(IdentityConflict):
                    await link_existing_identity(db, actor_user_id=actor, proof=proof)
        self.assertEqual(tuple(await self.counts()), (0, 0, 3))

    async def test_line_namespace_does_not_implicitly_share_subject_ownership(self):
        await self.link()
        await self.link(proof=self.line)
        other_namespace = replace(self.line, namespace="different-reviewed-provider")
        async with self.sessions() as db:
            with self.assertRaisesRegex(IdentityConflict, "line_link_required"):
                await resolve_identity_owner(db, other_namespace)
        with self.assertRaisesRegex(IdentityConflict, "provider_already_linked"):
            await self.link(proof=other_namespace)
        self.assertEqual(tuple(await self.counts()), (2, 2, 3))

    async def test_subject_claim_race_has_exactly_one_owner_and_event(self):
        outcomes = await asyncio.wait_for(asyncio.gather(self.link(1), self.link(2), return_exceptions=True), timeout=15)
        self.assertEqual(sum(isinstance(x, int) for x in outcomes), 1)
        self.assertEqual(sum(isinstance(x, IdentityConflict) for x in outcomes), 1)
        self.assertEqual(tuple(await self.counts()), (1, 1, 3))

    async def test_same_actor_concurrent_retry_is_idempotent(self):
        outcomes = await asyncio.wait_for(asyncio.gather(*(self.link() for _ in range(4))), timeout=15)
        self.assertEqual(len(set(outcomes)), 1)
        self.assertEqual(tuple(await self.counts()), (1, 1, 3))

    async def test_one_active_identity_per_provider(self):
        await self.link()
        with self.assertRaisesRegex(IdentityConflict, "provider_already_linked"):
            await self.link(proof=replace(self.google, subject="another"))

    async def test_replacement_retires_old_subject_permanently(self):
        old_id = await self.link()
        new = replace(self.google, subject="replacement")
        async with self.sessions.begin() as db:
            result = await replace_google_identity(db, actor_user_id=1, expected_identity_id=old_id,
                current_proof=self.google, new_proof=new, reason="Evaluator replacement test")
            self.assertNotEqual(result.id, old_id)
        async with self.sessions() as db:
            self.assertEqual(await resolve_identity_owner(db, new), 1)
            with self.assertRaisesRegex(IdentityConflict, "identity_retired"):
                await resolve_identity_owner(db, self.google)
        with self.assertRaisesRegex(IdentityConflict, "identity_retired"):
            await self.link(user=2)
        self.assertEqual(tuple(await self.counts()), (2, 3, 3))

    async def test_conflicting_replacement_leaves_current_access_intact(self):
        old_id = await self.link()
        other = replace(self.google, subject="other-user")
        await self.link(user=2, proof=other)
        async with self.sessions.begin() as db:
            with self.assertRaisesRegex(IdentityConflict, "identity_already_owned"):
                await replace_google_identity(db, actor_user_id=1, expected_identity_id=old_id,
                    current_proof=self.google, new_proof=other, reason="Conflict test")
        async with self.sessions() as db:
            self.assertEqual(await resolve_identity_owner(db, self.google), 1)
        self.assertEqual(tuple(await self.counts()), (2, 2, 3))

    async def test_failure_after_retirement_rolls_back_even_if_caller_commits(self):
        old_id = await self.link()
        async def fail(*args):
            raise IdentityConflict("simulated_insert_failure")
        async with self.sessions.begin() as db:
            with patch('src.route66_ext.services.auth.provider_identities._bind', fail):
                with self.assertRaises(IdentityConflict):
                    await replace_google_identity(db, actor_user_id=1, expected_identity_id=old_id,
                        current_proof=self.google, new_proof=replace(self.google, subject="new"), reason="Rollback test")
        async with self.sessions() as db:
            self.assertEqual(await resolve_identity_owner(db, self.google), 1)
        self.assertEqual(tuple(await self.counts()), (1, 1, 3))

    async def test_wrong_old_proof_and_stale_expectation_fail_without_changes(self):
        old_id = await self.link()
        for expected, current in [(old_id + 100, self.google), (old_id, replace(self.google, subject="not-current"))]:
            async with self.sessions.begin() as db:
                with self.assertRaises(IdentityConflict):
                    await replace_google_identity(db, actor_user_id=1, expected_identity_id=expected,
                        current_proof=current, new_proof=replace(self.google, subject="new"), reason="Denied")
        self.assertEqual(tuple(await self.counts()), (1, 1, 3))

    async def test_concurrent_replacements_keep_losing_users_original_identity(self):
        import src.route66_ext.services.auth.provider_identities as service
        first_id = await self.link()
        second_proof = replace(self.google, subject="second-user")
        second_id = await self.link(user=2, proof=second_proof)
        replacement = replace(self.google, subject="contested-replacement")
        original_bind = service._bind
        arrivals = 0
        ready = asyncio.Event()
        async def synchronized_bind(*args):
            nonlocal arrivals
            arrivals += 1
            if arrivals == 2:
                ready.set()
            await ready.wait()
            return await original_bind(*args)
        async def swap(user, expected, proof):
            async with self.sessions.begin() as db:
                result = await replace_google_identity(db, actor_user_id=user, expected_identity_id=expected,
                    current_proof=proof, new_proof=replacement, reason="Concurrent fixture")
                return result.id
        with patch.object(service, "_bind", synchronized_bind):
            results = await asyncio.wait_for(asyncio.gather(
                swap(1, first_id, self.google), swap(2, second_id, second_proof), return_exceptions=True), 15)
        self.assertEqual(sum(isinstance(x, int) for x in results), 1)
        self.assertEqual(sum(isinstance(x, IdentityConflict) for x in results), 1)
        winner = 1 if isinstance(results[0], int) else 2
        async with self.sessions() as db:
            self.assertEqual(await resolve_identity_owner(db, replacement), winner)
            self.assertEqual(await resolve_identity_owner(db, second_proof if winner == 1 else self.google), 3 - winner)
        self.assertEqual(tuple(await self.counts()), (3, 4, 3))

    async def test_outer_rollback_does_not_commit_a_binding_or_event(self):
        with self.assertRaisesRegex(RuntimeError, "abort fixture"):
            async with self.sessions.begin() as db:
                await link_existing_identity(db, actor_user_id=1, proof=self.google)
                raise RuntimeError("abort fixture")
        self.assertEqual(tuple(await self.counts()), (0, 0, 3))

    async def test_retirement_requires_nonnull_reason_at_database_boundary(self):
        await self.link()
        with self.assertRaises(DBAPIError):
            async with self.sessions.begin() as db:
                await db.exec(text('UPDATE provideridentity SET retired_at=now()'))
        async with self.sessions() as db:
            self.assertEqual(await resolve_identity_owner(db, self.google), 1)

    async def test_migration_rejects_wrong_bootstrap_unique_index(self):
        async with self.engine.begin() as conn:
            await conn.execute(text('DROP INDEX uq_provider_identity_active_user'))
            await conn.execute(text('CREATE UNIQUE INDEX uq_provider_identity_active_user ON provideridentity(id)'))
        with self.assertRaisesRegex(RuntimeError, "schema mismatch"):
            async with self.engine.begin() as conn:
                await conn.run_sync(migrate)

    async def test_database_guards_block_reassignment_deletion_and_audit_tampering(self):
        await self.link()
        statements = ["UPDATE provideridentity SET user_id=2", "UPDATE provideridentity SET subject='forged'",
            "DELETE FROM provideridentity", "TRUNCATE provideridentity CASCADE",
            "UPDATE provideridentityevent SET reason='forged'", "DELETE FROM provideridentityevent",
            "TRUNCATE provideridentityevent", 'DELETE FROM "user" WHERE id=1']
        for sql in statements:
            with self.subTest(sql=sql), self.assertRaises(DBAPIError):
                async with self.sessions.begin() as db:
                    await db.exec(text(sql))
        self.assertEqual(tuple(await self.counts()), (1, 1, 3))

    async def test_retirement_cannot_be_reversed(self):
        old_id = await self.link()
        async with self.sessions.begin() as db:
            await replace_google_identity(db, actor_user_id=1, expected_identity_id=old_id,
                current_proof=self.google, new_proof=replace(self.google, subject="new"), reason="Test")
        with self.assertRaises(DBAPIError):
            async with self.sessions.begin() as db:
                await db.exec(text('UPDATE provideridentity SET retired_at=NULL, retirement_reason=NULL WHERE id=:id'), params={"id": old_id})

    async def test_migration_reruns_and_nonempty_downgrade_refuses(self):
        await self.link()
        async with self.engine.begin() as conn:
            await conn.run_sync(migrate)
        with self.assertRaisesRegex(RuntimeError, "Cannot downgrade"):
            async with self.engine.begin() as conn:
                await conn.run_sync(lambda c: migrate(c, "downgrade"))
        self.assertEqual(tuple(await self.counts()), (1, 1, 3))

    async def test_create_all_first_bootstrap_and_empty_downgrade(self):
        self.assertEqual(GUARD_DDL, MIGRATION.GUARD_DDL)
        self.assertEqual(EVENT_GUARD_DDL, MIGRATION.EVENT_GUARD_DDL)
        async with self.engine.begin() as conn:
            await conn.run_sync(lambda c: migrate(c, "downgrade"))
            await conn.run_sync(ProviderIdentity.__table__.create)
            await conn.run_sync(ProviderIdentityEvent.__table__.create)
            await conn.run_sync(migrate)
        await self.link()
        with self.assertRaises(DBAPIError):
            async with self.sessions.begin() as db:
                await db.exec(text('DELETE FROM provideridentityevent'))


if __name__ == "__main__":
    unittest.main()

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
