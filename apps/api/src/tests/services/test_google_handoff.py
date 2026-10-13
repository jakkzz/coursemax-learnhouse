"""Offline Google handoff: real transactions, RSA proof and mocked fixed endpoints."""
import asyncio
import base64
from dataclasses import fields, replace
import hashlib
import json
import os
import time
import unittest
import uuid
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt

from src.services.auth.google_handoff import (
    GOOGLE_TOKEN_URL, GoogleHandoffConfig, GoogleHandoffError, complete_google_handoff,
)
from src.services.auth.oauth_transactions import OAuthClient, OAuthTransactions, LinkActor
from src.services.auth.provider_proof import GOOGLE_JWKS_URL, MAX_TOKEN_BYTES


class Store:
    def __init__(self):
        self.records = {}

    async def create(self, key, value, ttl):
        if key in self.records:
            return False
        self.records[key] = value
        return True

    async def consume(self, key, guard):
        raw = self.records.get(key)
        if raw is None or json.loads(raw)['guard'] != guard:
            return None
        return self.records.pop(key)


class GoogleHandoffTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.jwk = jwt.algorithms.RSAAlgorithm.to_jwk(cls.key.public_key(), as_dict=True)
        cls.jwk.update(kid='fixture', alg='RS256', use='sig')

    def setUp(self):
        self.oauth = OAuthClient('google', 'fixture-client', 'https://learn.example.com', 'global')
        self.config = GoogleHandoffConfig(self.oauth, 'fixture-secret')
        self.store = Store()
        self.transactions = OAuthTransactions(self.store, deployment='fixture', secret=b'x' * 32)
        self.requests = []
        self.claim_changes = {}
        self.token_response = None
        self.delay_endpoint = None
        self.delay_seconds = 0.05
        self.intent = 'signin'
        self.actor = None

    async def start(self, intent='signin', actor=None):
        self.intent, self.actor = intent, actor
        self.started = await self.transactions.begin(
            self.oauth, intent=intent, actor=actor, return_path='/dashboard?tab=private',
        )
        self.auth_params = parse_qs(urlsplit(self.started.authorization_url).query)

    async def handler(self, request):
        self.requests.append(request)
        url = str(request.url)
        self.assertIn(url, (GOOGLE_TOKEN_URL, GOOGLE_JWKS_URL))
        for header in ('authorization', 'cookie', 'x-internal-key'):
            self.assertNotIn(header, request.headers)
        if url == self.delay_endpoint:
            await asyncio.sleep(self.delay_seconds)
        if url == GOOGLE_JWKS_URL:
            self.assertEqual(request.method, 'GET')
            return httpx.Response(200, json={'keys': [self.jwk]})
        self.assertEqual(request.method, 'POST')
        data = parse_qs(request.content.decode())
        self.assertEqual(data['client_id'], ['fixture-client'])
        self.assertEqual(data['client_secret'], ['fixture-secret'])
        self.assertEqual(data['redirect_uri'], [self.oauth.callback_uri])
        self.assertEqual(data['grant_type'], ['authorization_code'])
        self.assertEqual(data['code'], ['fixture-code'])
        self.assertEqual(set(data), {'client_id', 'client_secret', 'redirect_uri', 'grant_type', 'code', 'code_verifier'})
        challenge = base64.urlsafe_b64encode(hashlib.sha256(data['code_verifier'][0].encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(challenge, self.auth_params['code_challenge'][0])
        if self.token_response is not None:
            return self.token_response
        now = int(time.time())
        claims = dict(iss='https://accounts.google.com', aud='fixture-client', sub='fixture-subject',
                      iat=now - 1, exp=now + 120, nonce=self.auth_params['nonce'][0],
                      email='personal@gmail.com', email_verified=True)
        claims.update(self.claim_changes)
        token = jwt.encode(claims, self.key, algorithm='RS256', headers={'kid': 'fixture'})
        return httpx.Response(200, json={'id_token': token, 'access_token': 'discard-access', 'refresh_token': 'discard-refresh'})

    async def finish(self, **overrides):
        # Deliberately poisoned shared client: provider helpers must strip these.
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(self.handler), auth=('native', 'password'),
            cookies={'LH_access': 'native-token'}, headers={'X-Internal-Key': 'internal-secret'},
        ) as client:
            args = dict(state=self.started.state, browser_cookie=self.started.browser_cookie,
                        intent=self.intent, actor=self.actor, code='fixture-code', client=client)
            config = overrides.pop('config', self.config)
            args.update(overrides)
            return await complete_google_handoff(self.transactions, config, **args)

    async def assert_spent(self):
        count = len(self.requests)
        with self.assertRaisesRegex(GoogleHandoffError, '^invalid_oauth_transaction$'):
            await self.finish()
        self.assertEqual(len(self.requests), count)

    def test_config_normalizes_explicit_emails_without_domain_policy(self):
        config = replace(self.config, registration_emails=frozenset({'Personal@GMAIL.COM', 'Staff@Example.AC.TH'}))
        self.assertEqual(config.registration_emails, frozenset({'personal@gmail.com', 'staff@example.ac.th'}))
        self.assertNotIn('fixture-secret', repr(config))
        self.assertNotIn('personal@gmail.com', repr(config))

    def test_invalid_config_is_redacted(self):
        variants = [dict(client_secret=value) for value in ('', ' secret', 'secret\n', 'é', 'x' * 256)]
        variants += [dict(registration_emails=value) for value in (
            {'a@example.com'}, frozenset({'not-email'}), frozenset({None}), frozenset({b'a@example.com'}),
        )]
        variants += [dict(client=OAuthClient('line', 'fixture', 'https://learn.example.com', 'reviewed-provider'))]
        for changes in variants:
            with self.subTest(changes=list(changes)), self.assertRaisesRegex(GoogleHandoffError, '^invalid_google_configuration$'):
                replace(self.config, **changes)

    async def test_signin_returns_proof_only_without_registration_permission(self):
        await self.start()
        result = await self.finish()
        self.assertEqual(result.proof.subject, 'fixture-subject')
        self.assertEqual(result.intent, 'signin')
        self.assertEqual(result.return_path, '/dashboard?tab=private')
        self.assertEqual({f.name for f in fields(result)}, {'proof', 'intent', 'return_path', 'actor'})
        for secret in ('fixture-subject', 'personal@gmail.com', 'private', 'discard-access', 'discard-refresh'):
            self.assertNotIn(secret, repr(result))
        self.assertEqual([str(r.url) for r in self.requests], [GOOGLE_TOKEN_URL, GOOGLE_JWKS_URL])
        await self.assert_spent()

    async def test_personal_and_institutional_google_addresses_can_register_if_listed(self):
        for email in ('personal@gmail.com', 'staff@example.ac.th'):
            await self.start('register')
            self.claim_changes = {'email': email}
            config = replace(self.config, registration_emails=frozenset({email.upper()}))
            result = await self.finish(config=config)
            self.assertEqual(result.proof.verified_email, email)
            self.assertFalse(hasattr(result, 'role'))
            self.assertFalse(hasattr(result, 'institution_verified'))

    async def test_registration_is_deny_by_default_and_no_domain_wildcard(self):
        for allowlist in (frozenset(), frozenset({'someone@gmail.com'}), frozenset({'teacher@example.ac.th'})):
            await self.start('register')
            with self.assertRaises(GoogleHandoffError):
                await self.finish(config=replace(self.config, registration_emails=allowlist))
            await self.assert_spent()

    async def test_cancellation_and_missing_invalid_code_are_consumed_without_network(self):
        for change in ({'provider_error': 'access_denied'}, {'provider_error': 'secret-provider-detail'},
                       {'provider_error': ''}, {'code': None}, {'code': ''}, {'code': ' '},
                       {'code': 'code\n'}, {'code': 'é'}, {'code': 'x' * 4097}):
            await self.start()
            with self.assertRaises(GoogleHandoffError) as error:
                await self.finish(**change)
            self.assertNotIn('secret-provider-detail', str(error.exception))
            self.assertEqual(self.requests, [])
            await self.assert_spent()

    async def test_wrong_browser_or_client_does_not_burn_legitimate_transaction(self):
        for changes in (
            {'browser_cookie': 'x' * 43},
            {'config': replace(self.config, client=replace(self.oauth, client_id='other-client'))},
            {'config': replace(self.config, client=replace(self.oauth, public_origin='https://other.example.com'))},
            {'intent': 'register'},
        ):
            await self.start()
            count = len(self.requests)
            with self.assertRaisesRegex(GoogleHandoffError, '^invalid_oauth_transaction$'):
                await self.finish(**changes)
            self.assertEqual(len(self.requests), count)
            self.assertEqual((await self.finish()).proof.subject, 'fixture-subject')

    async def test_link_preserves_server_actor_and_rejects_wrong_account_or_session(self):
        actor = LinkActor(42, 'a' * 64)
        await self.start('link', actor)
        for wrong in (LinkActor(43, 'a' * 64), LinkActor(42, 'b' * 64)):
            with self.assertRaises(GoogleHandoffError):
                await self.finish(actor=wrong)
        self.assertEqual(self.requests, [])
        result = await self.finish()
        self.assertEqual(result.actor, actor)
        self.assertEqual(result.intent, 'link')
        self.assertNotIn('a' * 64, repr(result))

    async def test_non_object_malformed_unicode_and_oversized_responses_fail_closed(self):
        for body in (b'[]', b'null', b'not-json', b'\xff', b'x' * (65536 + 1)):
            await self.start()
            self.token_response = httpx.Response(200, content=body)
            with self.assertRaisesRegex(GoogleHandoffError, '^provider_unavailable$'):
                await self.finish()
            await self.assert_spent()

    async def test_redirect_provider_errors_and_rate_limit_are_not_followed(self):
        for status in (301, 302, 400, 401, 429, 500):
            await self.start()
            self.token_response = httpx.Response(status, headers={'Location': 'https://attacker.example'}, json={'error': 'SECRET'})
            before = len(self.requests)
            with self.assertRaisesRegex(GoogleHandoffError, '^provider_unavailable$'):
                await self.finish()
            self.assertEqual(len(self.requests), before + 1)
            await self.assert_spent()

    async def test_missing_invalid_or_oversized_id_token_is_consumed(self):
        for token in (None, 7, '', 'é', 'x' * (MAX_TOKEN_BYTES + 1), 'not.a.jwt'):
            await self.start()
            self.token_response = httpx.Response(200, json={'id_token': token})
            with self.assertRaisesRegex(GoogleHandoffError, '^invalid_provider_token$'):
                await self.finish()
            await self.assert_spent()

    async def test_real_nonce_audience_email_and_signature_rejections(self):
        for changes in ({'nonce': 'wrong'}, {'aud': 'other-client'}, {'email_verified': False}, {'iss': 'https://attacker.example'}):
            await self.start()
            self.claim_changes = changes
            with self.assertRaisesRegex(GoogleHandoffError, '^invalid_provider_token$'):
                await self.finish()
            await self.assert_spent()
        await self.start()
        self.claim_changes = {}
        with patch.object(self, 'jwk', {**self.jwk, 'kid': 'unknown-key'}):
            with self.assertRaises(GoogleHandoffError):
                await self.finish()
        await self.assert_spent()

    async def test_provider_deadline_and_handoff_deadline_cover_token_and_jwks(self):
        for endpoint in (GOOGLE_TOKEN_URL, GOOGLE_JWKS_URL):
            await self.start()
            self.delay_endpoint = endpoint
            with patch('src.services.auth.provider_proof.PROVIDER_TIMEOUT_SECONDS', 0.01):
                with self.assertRaisesRegex(GoogleHandoffError, '^provider_unavailable$'):
                    await self.finish()
            await self.assert_spent()
            await self.start()
            with patch('src.services.auth.google_handoff.HANDOFF_TIMEOUT_SECONDS', 0.01):
                with self.assertRaisesRegex(GoogleHandoffError, '^provider_unavailable$'):
                    await self.finish()
            await self.assert_spent()

    async def test_task_cancellation_propagates_and_does_not_revive_transaction(self):
        await self.start()
        entered = asyncio.Event()
        async def waiting(request):
            entered.set()
            await asyncio.sleep(60)
        async with httpx.AsyncClient(transport=httpx.MockTransport(waiting)) as client:
            task = asyncio.create_task(complete_google_handoff(
                self.transactions, self.config, state=self.started.state,
                browser_cookie=self.started.browser_cookie, intent='signin', code='fixture-code', client=client,
            ))
            await asyncio.wait_for(entered.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        await self.assert_spent()

    async def test_concurrent_callbacks_exchange_exactly_once(self):
        await self.start()
        results = await asyncio.gather(*(self.finish() for _ in range(8)), return_exceptions=True)
        self.assertEqual(sum(not isinstance(result, Exception) for result in results), 1)
        self.assertEqual(sum(isinstance(result, GoogleHandoffError) for result in results), 7)
        self.assertEqual(len(self.requests), 2)


@unittest.skipUnless(os.getenv('RUN_OAUTH_REDIS_TESTS') == '1', 'requires isolated Redis harness')
class GoogleHandoffRedisTests(GoogleHandoffTests):
    """Repeat the full handoff matrix with the real atomic Redis transaction store."""

    async def asyncSetUp(self):
        from redis.asyncio import Redis
        from src.services.auth.oauth_transactions import RedisTransactionStore
        if os.environ.get('OAUTH_TEST_REDIS_SOCKET') != '/scratch/redis.sock':
            raise RuntimeError('Use the isolated Unix-socket harness')
        self.redis = Redis(unix_socket_path='/scratch/redis.sock')
        await self.redis.ping()
        self.transactions = OAuthTransactions(
            RedisTransactionStore(self.redis), deployment='handoff-' + uuid.uuid4().hex,
            secret=b'x' * 32,
        )

    async def asyncTearDown(self):
        await self.redis.aclose()


if __name__ == '__main__':
    unittest.main()
