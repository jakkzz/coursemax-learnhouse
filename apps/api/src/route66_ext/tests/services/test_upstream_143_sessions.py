"""Merged upstream/native + provider contracts; synthetic credentials, no network."""
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException, Response
from starlette.requests import Request
from src.db.users import User
from src.security.auth import decode_jwt
from src.services.auth import session
from src.routers.mfa import _rotate_sessions
from src.route66_ext.security.provider_session import claims


class SessionCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.user = User(id=77, email='fixture@example.invalid', user_uuid='user_fixture')
        self.values = {}
        self.redis = Mock()
        self.redis.get.side_effect = self.values.get
        def consume(key, value, **kwargs):
            if key in self.values:
                return False
            self.values[key] = value
            return True
        self.redis.set.side_effect = consume
        self.redis_patch = patch('src.core.redis.get_redis_client', return_value=self.redis)
        self.redis_patch.start()
        self.addCleanup(self.redis_patch.stop)

    def pending(self, method='google'):
        return session.create_mfa_pending_token(self.user.email, method, 1, True,
            provider_claims=claims(self.user, 9, auth_time=1234))

    async def test_provider_challenge_preserves_subject_and_domain(self):
        for method in ('google', 'line'):
            token = self.pending(method)
            payload = decode_jwt(token)
            self.assertEqual(payload['sub'], 'lh:user:77')
            self.assertEqual(payload['lh_identity'], 9)
            self.assertEqual(payload['lh_auth_time'], 1234)
            self.assertTrue(payload['cdm'])
            self.assertEqual(len(payload['jti']), 43)
            self.assertTrue(await session.mfa_pending_token_usable(None, token))

    async def test_provider_spend_uses_existing_ledger_and_rejects_replay(self):
        token = self.pending()
        with patch('src.services.auth.link_tokens.redeem_link_token', new=AsyncMock()) as sql:
            self.assertTrue(await session.spend_mfa_pending_token(None, token))
            self.assertFalse(await session.mfa_pending_token_usable(None, token))
            with self.assertRaises(HTTPException) as error:
                await session.spend_mfa_pending_token(None, token)
            self.assertEqual(error.exception.status_code, 401)
            sql.assert_not_called()

    async def test_old_provider_spend_is_not_forgotten_after_upgrade(self):
        token = self.pending()
        self.values['lh:mfa:used:' + decode_jwt(token)['jti']] = '1'
        self.assertFalse(await session.mfa_pending_token_usable(None, token))

    async def test_provider_store_outage_is_not_treated_as_unused(self):
        self.redis.get.side_effect = RuntimeError('synthetic outage')
        with self.assertRaises(HTTPException) as error:
            await session.mfa_pending_token_usable(None, self.pending())
        self.assertEqual(error.exception.status_code, 503)

    async def test_native_challenge_uses_upstream_durable_spend(self):
        token = session.create_mfa_pending_token(self.user.email, 'password', 1, True)
        self.assertEqual(len(decode_jwt(token)['jti']), 22)
        with patch('src.services.auth.link_tokens.link_token_spent', new=AsyncMock(return_value=False)) as lookup, \
             patch('src.services.auth.link_tokens.redeem_link_token', new=AsyncMock(return_value=True)) as spend:
            self.assertTrue(await session.mfa_pending_token_usable(None, token))
            self.assertTrue(await session.spend_mfa_pending_token(None, token))
            lookup.assert_awaited_once()
            spend.assert_awaited_once()
            self.redis.set.assert_not_called()

    async def test_provider_issuance_keeps_both_native_and_owned_arguments(self):
        for active in (False, True):
            with patch.object(session, 'is_mfa_active', new=AsyncMock(return_value=active)):
                result = await session.issue_session_or_challenge(None, self.user, 'google', 1,
                    custom_domain=True, provider_identity_id=9)
            payload = decode_jwt(result.mfa_token if active else result.access_token)
            self.assertEqual(payload['sub'], 'lh:user:77')
            self.assertTrue(payload['cdm'])
            self.assertEqual(payload['lh_identity'], 9)

    async def test_no_email_only_provider_issuance(self):
        with self.assertRaises(ValueError):
            await session.issue_session_or_challenge(None, self.user, 'google', 1)

    def test_mfa_rotation_preserves_provider_identity_and_original_auth_time(self):
        for method in ('google', 'line'):
            original = session.mint_session_tokens(self.user.email, method, 1, True,
                provider_claims=claims(self.user, 9, auth_time=1234))
            request = Request({'type': 'http', 'scheme': 'https', 'method': 'POST',
                'path': '/api/v1/auth/mfa/confirm', 'server': ('learn.example.com', 443),
                'headers': [(b'host', b'learn.example.com'),
                            (b'cookie', ('LH_access=' + original.access_token).encode())]})
            with patch('src.routers.mfa.revoke_user_sessions_before') as revoke:
                result = _rotate_sessions(request, Response(), self.user)
            revoke.assert_called_once_with(77)
            for key in ('access_token', 'refresh_token'):
                payload = decode_jwt(result[key])
                self.assertIsNotNone(payload)
                self.assertEqual(payload['sub'], 'lh:user:77')
                self.assertEqual(payload['amr'], method)
                self.assertEqual(payload['lh_identity'], 9)
                self.assertEqual(payload['lh_auth_time'], 1234)
                self.assertTrue(payload['cdm'])


if __name__ == '__main__':
    unittest.main()
