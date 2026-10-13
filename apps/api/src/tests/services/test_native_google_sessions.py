"""Native Google integration on isolated PostgreSQL; no provider accounts/network."""
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone
import os
import unittest
import httpx
import jwt
from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import text
from starlette.requests import Request

from src.tests.services import test_provider_identities_postgres as fixture
from src.db.organizations import Organization
from src.db.roles import Role
from src.db.user_organizations import UserOrganization
from src.db.users import User
from src.services.auth.google_handoff import VerifiedGoogleHandoff
from src.services.auth.native_google import complete_native_google
from src.services.auth.oauth_transactions import LinkActor
from src.security.auth import decode_jwt, decode_refresh_token, get_current_user, create_access_token
from src.security.provider_session import resolve_provider_session, claims


class RedisFixture:
    def __init__(self):
        self.data = {}
        self.unavailable = False

    def get(self, key):
        if self.unavailable:
            raise RuntimeError('fixture outage')
        return self.data.get(key)

    def setex(self, key, ttl, value):
        if self.unavailable:
            raise RuntimeError('fixture outage')
        self.data[key] = value
        return True

    def set(self, key, value, nx=False, ex=None):
        if self.unavailable:
            raise RuntimeError('fixture outage')
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    def ping(self):
        if self.unavailable:
            raise RuntimeError('fixture outage')
        return True


def request(access=None, refresh=None):
    cookies = []
    if access:
        cookies.append('LH_access=' + access)
    if refresh:
        cookies.append('LH_refresh=' + refresh)
    return Request({'type': 'http', 'method': 'POST', 'path': '/api/v1/auth/login',
                    'scheme': 'https', 'server': ('learn.example.com', 443),
                    'client': ('127.0.0.1', 1000), 'query_string': b'',
                    'headers': [(b'host', b'learn.example.com'), (b'cookie', '; '.join(cookies).encode())]})


@unittest.skipUnless(os.getenv('RUN_IDENTITY_POSTGRES_TESTS') == '1', 'isolated PostgreSQL required')
class NativeGoogleTests(fixture.ProviderIdentityPostgresTests):
    @classmethod
    def setUpClass(cls):
        from cryptography.hazmat.primitives.asymmetric import rsa
        cls.google_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.google_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(cls.google_key.public_key(), as_dict=True)
        cls.google_jwk.update(kid='native-fixture', use='sig', alg='RS256')

    async def asyncSetUp(self):
        await super().asyncSetUp()
        async with self.engine.begin() as conn:
            for table in (Organization.__table__, Role.__table__, UserOrganization.__table__):
                await conn.run_sync(table.create)
        async with self.sessions.begin() as db:
            db.add(Organization(id=1, name='Fixture', slug='default', email='fixture@example.com', org_uuid='org_fixture'))
            db.add(Role(id=4, name='Learner', role_uuid='role_fixture', rights={'dashboard': {'action_access': False}}))
            await db.flush()
            for ident in (1, 2, 3):
                db.add(UserOrganization(user_id=ident, org_id=1, role_id=4, creation_date='fixture', update_date='fixture'))
        async with self.engine.begin() as conn:
            # Parent fixture inserts explicit IDs; advance only this disposable sequence.
            await conn.execute(text("SELECT setval(pg_get_serial_sequence('\"user\"', 'id'), 3, true)"))
        self.redis = RedisFixture()
        self.patches = [
            patch('src.core.redis.get_redis_client', return_value=self.redis),
            patch('src.services.orgs.auth_policy.enforce_login_auth_method', new=AsyncMock()),
            patch('src.services.auth.native_google.enforce_login_auth_method', new=AsyncMock()),
            patch('src.security.features_utils.usage.check_limits_with_usage', new=AsyncMock()),
            patch('src.services.auth.session.is_mfa_active', new=AsyncMock(return_value=False)),
        ]
        for p in self.patches:
            p.start()

    async def asyncTearDown(self):
        for p in reversed(self.patches):
            p.stop()
        await super().asyncTearDown()

    async def login(self, proof=None, intent='signin', actor=None):
        verified = VerifiedGoogleHandoff(proof or self.google, intent, '/home', actor)
        async with self.sessions.begin() as db:
            user, result = await complete_native_google(db, verified, org_id=1)
            return user.id, result

    async def test_google_sessions_resolve_native_user_without_email_subject(self):
        await self.link()
        user_id, result = await self.login()
        payload = decode_jwt(result.access_token)
        self.assertEqual(payload['sub'], 'lh:user:1')
        self.assertEqual(payload['amr'], 'google')
        self.assertEqual(payload['sorg'], 1)
        self.assertEqual(payload['purpose'], 'session')
        self.assertEqual(decode_refresh_token(result.refresh_token)['sub'], 'lh:user:1')
        async with self.sessions() as db:
            current = await get_current_user(request(result.access_token), db)
            self.assertEqual(current.id, user_id)
        for change in ({'iss': 'https://other.example.com'}, {'aud': 'other'}, {'lh_identity': True}, {'lhv': '2'}, {'lh_uuid': ''}):
            token = create_access_token({**payload, **change})
            self.assertIsNone(decode_jwt(token))

    async def test_link_does_not_change_password_email_or_roles(self):
        original = None
        async with self.sessions() as db:
            original = (await db.get(User, 1)).model_dump()
        actor = LinkActor(1, 'a' * 64)
        ident, result = await self.login(intent='link', actor=actor)
        self.assertEqual(ident, 1)
        async with self.sessions() as db:
            self.assertEqual((await db.get(User, 1)).model_dump(), original)
        self.assertEqual(tuple(await self.counts()), (1, 1, 3))

    async def test_registration_atomically_creates_learner_and_binding(self):
        ident, result = await self.login(intent='register')
        async with self.sessions() as db:
            user = await db.get(User, ident)
            self.assertFalse(user.password)
            self.assertFalse(user.is_superadmin)
            self.assertTrue(user.email_verified)
            current = await get_current_user(request(result.access_token), db)
            self.assertEqual(current.id, ident)
        self.assertEqual(tuple(await self.counts()), (1, 1, 4))
        with self.assertRaises(HTTPException):
            await self.login(intent='register')
        self.assertEqual(tuple(await self.counts()), (1, 1, 4))

    async def test_existing_email_requires_link_not_merge_or_creation(self):
        proof = replace(self.google, verified_email='fixture1@example.com')
        with self.assertRaises(HTTPException) as error:
            await self.login(proof, 'register')
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(tuple(await self.counts()), (0, 0, 3))
        with self.assertRaises(HTTPException):
            await self.login(proof)

    async def test_failed_session_issuance_rolls_back_account_and_identity(self):
        with patch('src.services.auth.native_google.issue_session_or_challenge', new=AsyncMock(side_effect=RuntimeError('fixture'))):
            with self.assertRaises(RuntimeError):
                await self.login(intent='register')
        self.assertEqual(tuple(await self.counts()), (0, 0, 3))

    async def test_changed_google_email_keeps_same_account_and_native_contact(self):
        await self.link()
        _, result = await self.login(replace(self.google, verified_email='new@gmail.com'))
        async with self.sessions() as db:
            current = await get_current_user(request(result.access_token), db)
            self.assertEqual(current.email, 'fixture1@example.com')

    async def test_retired_identity_revokes_existing_access_and_pending_tokens(self):
        old = await self.link()
        _, result = await self.login()
        async with self.sessions.begin() as db:
            from src.services.auth.provider_identities import replace_google_identity
            await replace_google_identity(db, actor_user_id=1, expected_identity_id=old,
                current_proof=self.google, new_proof=replace(self.google, subject='replacement'), reason='fixture')
        async with self.sessions() as db:
            with self.assertRaises(HTTPException):
                await get_current_user(request(result.access_token), db)
            with self.assertRaises(HTTPException):
                await resolve_provider_session(db, decode_refresh_token(result.refresh_token))

    async def test_lockout_membership_removal_and_storage_failure_deny_existing_sessions(self):
        await self.link()
        _, result = await self.login()
        self.redis.unavailable = True
        async with self.sessions() as db:
            with self.assertRaises(HTTPException) as failure:
                await get_current_user(request(result.access_token), db)
            self.assertEqual(failure.exception.status_code, 503)
        self.redis.unavailable = False
        async with self.sessions.begin() as db:
            await db.exec(text("UPDATE \"user\" SET locked_until='2099-01-01T00:00:00+00:00' WHERE id=1"))
        async with self.sessions() as db:
            with self.assertRaises(HTTPException):
                await get_current_user(request(result.access_token), db)
        async with self.sessions.begin() as db:
            await db.exec(text('UPDATE "user" SET locked_until=NULL WHERE id=1'))
            await db.exec(text('DELETE FROM userorganization WHERE user_id=1'))
        async with self.sessions() as db:
            with self.assertRaises(HTTPException):
                await get_current_user(request(result.access_token), db)

    async def test_refresh_and_logout_preserve_subject_and_revoke_tokens(self):
        from fastapi import Response
        from src.routers.auth import refresh, logout
        await self.link()
        _, result = await self.login()
        with patch('src.routers.auth.check_refresh_rate_limit', return_value=(True, 0)):
            async with self.sessions() as db:
                refreshed = await refresh(request(refresh=result.refresh_token), Response(), db)
        self.assertEqual(decode_jwt(refreshed['access_token'])['lh_identity'], decode_jwt(result.access_token)['lh_identity'])
        self.assertEqual(decode_refresh_token(refreshed['refresh_token'])['sub'], 'lh:user:1')
        async with self.sessions() as db:
            await logout(request(refreshed['access_token'], refreshed['refresh_token']), Response(), db)
        async with self.sessions() as db:
            with self.assertRaises(HTTPException):
                await get_current_user(request(result.access_token), db)
        # A new login after logout must work even within the same second.
        _, fresh = await self.login()
        self.assertIsInstance(decode_jwt(fresh.access_token)['iat'], float)
        async with self.sessions() as db:
            self.assertEqual((await get_current_user(request(fresh.access_token), db)).id, 1)

    async def test_mfa_challenge_is_inert_then_completes_same_subject(self):
        from fastapi import Response
        from types import SimpleNamespace
        from src.routers.mfa import api_login_mfa, MFALoginRequest
        await self.link()
        with patch('src.services.auth.session.is_mfa_active', new=AsyncMock(return_value=True)):
            _, result = await self.login()
        self.assertTrue(result.mfa_required)
        self.assertIsNone(result.access_token)
        pending = decode_jwt(result.mfa_token)
        self.assertEqual(pending['sub'], 'lh:user:1')
        async with self.sessions() as db:
            with self.assertRaises(HTTPException):
                await get_current_user(request(result.mfa_token), db)
        with patch('src.routers.mfa._check_mfa_rate_limit'), \
             patch('src.routers.mfa.get_user_mfa', new=AsyncMock(return_value=SimpleNamespace(confirmed_at='yes'))), \
             patch('src.routers.mfa.consume_backup_code', new=AsyncMock(return_value=True)), \
             patch('src.routers.mfa.count_unused_backup_codes', new=AsyncMock(return_value=3)):
            async with self.sessions() as db:
                completed = await api_login_mfa(request(), Response(), MFALoginRequest(
                    mfa_token=result.mfa_token, code='fixture-backup', is_backup_code=True), db)
        payload = decode_jwt(completed['tokens']['access_token'])
        self.assertEqual(payload['sub'], 'lh:user:1')
        self.assertEqual(payload['purpose'], 'session')
        self.assertEqual(payload['lh_identity'], pending['lh_identity'])
        from src.security.provider_session import consume_mfa_challenge
        with self.assertRaises(HTTPException) as replay:
            consume_mfa_challenge(pending)
        self.assertEqual(replay.exception.status_code, 401)

    async def test_logout_storage_failure_is_not_success_and_blocked_users_can_logout(self):
        from fastapi import Response
        from src.routers.auth import logout
        await self.link()
        _, result = await self.login()
        self.redis.unavailable = True
        async with self.sessions() as db:
            with self.assertRaises(HTTPException) as failure:
                await logout(request(result.access_token), Response(), db)
            self.assertEqual(failure.exception.status_code, 503)
        self.redis.unavailable = False
        async with self.sessions.begin() as db:
            await db.exec(text('DELETE FROM userorganization WHERE user_id=1'))
        async with self.sessions() as db:
            response = Response()
            await logout(request(result.access_token), response, db)
            self.assertIn('jwt_revoked_before:1', self.redis.data)
            self.assertIn('set-cookie', response.headers)

    async def test_mfa_storage_failure_and_missing_identifier_fail_closed(self):
        from src.security.provider_session import consume_mfa_challenge
        await self.link()
        with patch('src.services.auth.session.is_mfa_active', new=AsyncMock(return_value=True)):
            _, result = await self.login()
        pending = decode_jwt(result.mfa_token)
        self.redis.unavailable = True
        with self.assertRaises(HTTPException) as failure:
            consume_mfa_challenge(pending)
        self.assertEqual(failure.exception.status_code, 503)
        self.redis.unavailable = False
        with self.assertRaises(HTTPException) as missing:
            consume_mfa_challenge({**pending, 'jti': None})
        self.assertEqual(missing.exception.status_code, 401)
        consume_mfa_challenge(pending)

    @asynccontextmanager
    async def http_flow(self, allow_registration=True, public_registration=False):
        from fastapi import FastAPI, Depends
        from types import SimpleNamespace
        from src.core.events.database import get_db_session
        from src.routers import google_subject_auth as google_router
        from src.services.auth.google_handoff import GoogleHandoffConfig, GOOGLE_TOKEN_URL
        from src.services.auth.provider_proof import GOOGLE_JWKS_URL
        from src.services.auth.oauth_transactions import OAuthClient, OAuthTransactions
        from src.tests.services.test_google_handoff import Store
        oauth = OAuthClient('google', 'native-test-client', 'https://learn.example.com', 'global')
        config = google_router.Settings(GoogleHandoffConfig(oauth, 'fixture-secret',
            frozenset({self.google.verified_email}) if allow_registration else frozenset(),
            public_registration=public_registration),
            1, 'native-http', b'x' * 32)
        store = Store()
        transactions = OAuthTransactions(store, deployment=config.deployment, secret=config.secret)
        self.google_requests = []
        self.nonce = None
        async def handler(req):
            self.google_requests.append(str(req.url))
            self.assertNotIn('authorization', req.headers)
            self.assertNotIn('cookie', req.headers)
            if str(req.url) == GOOGLE_JWKS_URL:
                return httpx.Response(200, json={'keys': [self.google_jwk]})
            self.assertEqual(str(req.url), GOOGLE_TOKEN_URL)
            form = parse_qs(req.content.decode())
            self.assertEqual(form['redirect_uri'], [oauth.callback_uri])
            now = int(datetime.now(timezone.utc).timestamp())
            token = jwt.encode({'iss': 'https://accounts.google.com', 'aud': oauth.client_id,
                'sub': self.google.subject, 'email': self.google.verified_email,
                'email_verified': True, 'nonce': self.nonce, 'iat': now - 1, 'exp': now + 120},
                self.google_key, algorithm='RS256', headers={'kid': 'native-fixture'})
            return httpx.Response(200, json={'id_token': token, 'access_token': 'never-to-browser'})
        @asynccontextmanager
        async def resources(_):
            yield SimpleNamespace(eval=AsyncMock(return_value=1)), transactions
        async def database():
            async with self.sessions() as db:
                yield db
        app = FastAPI()
        app.include_router(google_router.router, prefix='/auth/google')
        app.dependency_overrides[get_db_session] = database
        @app.get('/profile')
        async def profile(user=Depends(get_current_user)):
            return {'id': user.id}
        real_client = httpx.AsyncClient
        with patch.object(google_router, 'settings', return_value=config), \
             patch.object(google_router, 'resources', resources), \
             patch.object(google_router, 'httpx', SimpleNamespace(AsyncClient=lambda **kw: real_client(transport=httpx.MockTransport(handler)))):
            async with real_client(transport=httpx.ASGITransport(app=app), base_url='https://learn.example.com',
                                   headers={'Origin': oauth.public_origin}) as client:
                yield client

    async def start_http(self, client, intent, **extra):
        response = await client.post('/auth/google/start', json={'intent': intent, 'return_path': '/home', **extra})
        self.assertEqual(response.status_code, 200, response.text)
        authorization = parse_qs(urlsplit(response.json()['url']).query)
        self.nonce = authorization['nonce'][0]
        self.assertIn('__Host-LH_oauth_binding', client.cookies)
        self.assertNotIn('nonce', response.json())
        return {'state': authorization['state'][0], 'intent': intent, 'code': 'fixture-code'}

    async def test_http_google_registration_then_profile_and_replay_denial(self):
        async with self.http_flow() as client:
            body = await self.start_http(client, 'register')
            response = await client.post('/auth/google/complete', json=body)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn('never-to-browser', response.text)
            self.assertIn('LH_access', client.cookies)
            self.assertEqual((await client.get('/profile')).json()['id'], 4)
            token = response.json()['tokens']['access_token']
            self.assertEqual(decode_jwt(token)['sub'], 'lh:user:4')
            request_count = len(self.google_requests)
            replay = await client.post('/auth/google/complete', json=body)
            self.assertEqual(replay.status_code, 409)
            self.assertEqual(len(self.google_requests), request_count)
        self.assertEqual(tuple(await self.counts()), (1, 1, 4))

    async def test_http_public_registration_unlisted_email_creates_only_learner(self):
        from sqlmodel import select
        async with self.http_flow(allow_registration=False, public_registration=True) as client:
            self.assertEqual((await client.get('/auth/google/capabilities')).json(),
                             {'google': True, 'registration': True, 'public_registration': True})
            body = await self.start_http(client, 'register')
            response = await client.post('/auth/google/complete', json=body)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual((await client.get('/profile')).json()['id'], 4)
            # The same primary public action signs in the already-bound subject
            # without duplicating users, bindings, memberships or audit events.
            body = await self.start_http(client, 'register')
            returning = await client.post('/auth/google/complete', json=body)
            self.assertEqual(returning.status_code, 200, returning.text)
            self.assertEqual((await client.get('/profile')).json()['id'], 4)
        async with self.sessions() as db:
            membership = (await db.exec(select(UserOrganization).where(UserOrganization.user_id == 4))).one()
            self.assertEqual(membership.role_id, 4)
        self.assertEqual(tuple(await self.counts()), (1, 1, 4))

    async def test_http_standard_learner_discussion_creation_allows_public_signup(self):
        async with self.sessions.begin() as db:
            role = await db.get(Role, 4)
            rights = dict(role.rights) if isinstance(role.rights, dict) else role.rights.model_dump()
            rights['discussions'] = {'action_create': True, 'action_read': True,
                'action_update': False, 'action_update_own': True,
                'action_delete': False, 'action_delete_own': True}
            role.rights = rights
            db.add(role)
        async with self.http_flow(allow_registration=False, public_registration=True) as client:
            body = await self.start_http(client, 'register')
            response = await client.post('/auth/google/complete', json=body)
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(tuple(await self.counts()), (1, 1, 4))

    async def test_http_discussion_global_moderation_still_blocks_registration(self):
        async with self.sessions.begin() as db:
            role = await db.get(Role, 4)
            rights = dict(role.rights) if isinstance(role.rights, dict) else role.rights.model_dump()
            rights['discussions'] = {'action_create': True, 'action_update': True}
            role.rights = rights
            db.add(role)
        async with self.http_flow(allow_registration=False, public_registration=True) as client:
            body = await self.start_http(client, 'register')
            response = await client.post('/auth/google/complete', json=body)
            self.assertEqual(response.status_code, 503)
            self.assertIn('Learner role needs review', response.text)
        self.assertEqual(tuple(await self.counts()), (0, 0, 3))

    async def test_http_public_continue_never_merges_existing_email(self):
        from dataclasses import replace
        self.google = replace(self.google, verified_email='fixture1@example.com')
        async with self.http_flow(allow_registration=False, public_registration=True) as client:
            body = await self.start_http(client, 'register')
            response = await client.post('/auth/google/complete', json=body)
            self.assertEqual(response.status_code, 409)
            self.assertIn('already uses this email', response.text)
        self.assertEqual(tuple(await self.counts()), (0, 0, 3))

    async def test_http_cancel_consumes_state_and_unknown_signin_never_registers(self):
        async with self.http_flow() as client:
            body = await self.start_http(client, 'signin')
            cancel = await client.post('/auth/google/complete', json={**body, 'code': None, 'provider_error': 'access_denied'})
            self.assertEqual(cancel.status_code, 409)
            self.assertEqual(self.google_requests, [])
            replay = await client.post('/auth/google/complete', json=body)
            self.assertEqual(replay.status_code, 409)
            body = await self.start_http(client, 'signin')
            unknown = await client.post('/auth/google/complete', json=body)
            self.assertEqual(unknown.status_code, 409)
        self.assertEqual(tuple(await self.counts()), (0, 0, 3))

    async def test_http_link_requires_password_and_same_initiating_session(self):
        from src.security.security import security_hash_password
        async with self.sessions.begin() as db:
            user = await db.get(User, 1)
            user.password = security_hash_password('fixture-password')
            db.add(user)
        access = create_access_token({'sub': 'fixture1@example.com', 'purpose': 'session', 'amr': 'password', 'sorg': 1})
        async with self.http_flow() as client:
            client.cookies.set('LH_access', access, domain='learn.example.com', path='/')
            denied = await client.post('/auth/google/start', json={'intent': 'link', 'current_password': 'wrong'})
            self.assertEqual(denied.status_code, 401)
            body = await self.start_http(client, 'link', current_password='fixture-password')
            client.cookies.set('LH_access', create_access_token({'sub': 'fixture2@example.com', 'purpose': 'session'}), domain='learn.example.com', path='/')
            wrong = await client.post('/auth/google/complete', json=body)
            self.assertEqual(wrong.status_code, 409)
            self.assertEqual(self.google_requests, [])
            client.cookies.set('LH_access', access, domain='learn.example.com', path='/')
            linked = await client.post('/auth/google/complete', json=body)
            self.assertEqual(linked.status_code, 200, linked.text)
            self.assertEqual((await client.get('/profile')).json()['id'], 1)
        self.assertEqual(tuple(await self.counts()), (1, 1, 3))

    async def test_http_origin_cookie_ambiguity_and_signup_admission_fail_closed(self):
        async with self.http_flow(allow_registration=False) as client:
            denied = await client.post('/auth/google/start', json={'intent': 'register'})
            self.assertEqual(denied.status_code, 403)
            cross = await client.post('/auth/google/start', headers={'Origin': 'https://other.example.com'}, json={'intent': 'signin'})
            self.assertEqual(cross.status_code, 403)
            duplicate = await client.post('/auth/google/start', headers={'Cookie': 'LH_access=one; LH_access=two'}, json={'intent': 'signin'})
            self.assertEqual(duplicate.status_code, 400)
            missing = await client.post('/auth/google/start', headers={'Origin': ''}, json={'intent': 'signin'})
            self.assertEqual(missing.status_code, 403)
            self.assertEqual(self.google_requests, [])

    async def test_wrong_email_index_fails_registration_without_writes(self):
        async with self.engine.begin() as conn:
            await conn.execute(text('DROP INDEX uq_user_email_lower'))
            await conn.execute(text('CREATE UNIQUE INDEX uq_user_email_lower ON "user" (lower(username))'))
        with self.assertRaises(HTTPException) as failure:
            await self.login(intent='register')
        self.assertEqual(failure.exception.status_code, 503)
        self.assertEqual(tuple(await self.counts()), (0, 0, 3))

    async def test_email_migration_bootstrap_repeat_and_collision_refusal(self):
        import importlib.util
        from pathlib import Path
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        path = Path(__file__).resolve().parents[3] / 'migrations/versions/d84e13a6b902_native_google_email_uniqueness.py'
        spec = importlib.util.spec_from_file_location('native_email_migration_fixture', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        def upgrade(conn):
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()
        async with self.engine.begin() as conn:
            await conn.run_sync(upgrade)
            await conn.run_sync(upgrade)
            await conn.execute(text('DROP INDEX uq_user_email_lower'))
            await conn.run_sync(upgrade)
        async with self.engine.begin() as conn:
            await conn.execute(text('DROP INDEX uq_user_email_lower'))
        async with self.sessions.begin() as db:
            db.add(User(username='collision', first_name='', last_name='', email='FIXTURE1@EXAMPLE.COM', user_uuid='user_collision'))
        with self.assertRaises(RuntimeError):
            async with self.engine.begin() as conn:
                await conn.run_sync(upgrade)
        self.assertEqual(tuple(await self.counts()), (0, 0, 4))

    async def test_unique_email_constraint_blocks_mixed_case_duplicate(self):
        from sqlalchemy.exc import IntegrityError
        with self.assertRaises(IntegrityError):
            async with self.sessions.begin() as db:
                db.add(User(username='duplicate', first_name='', last_name='', email='FIXTURE1@EXAMPLE.COM', user_uuid='user_duplicate'))


if __name__ == '__main__':
    unittest.main()
