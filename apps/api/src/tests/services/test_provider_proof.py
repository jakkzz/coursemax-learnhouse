"""Offline tests: no provider accounts, network, database or session writes."""
import asyncio
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt

from src.services.auth.provider_proof import (
    GOOGLE_JWKS_URL, LINE_VERIFY_URL, MAX_RESPONSE_BYTES, MAX_TOKEN_BYTES,
    ProviderProofError, verify_google_id_token,
    verify_line_oauth_token, verify_line_liff_token,
)


class ProviderProofTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.jwk = jwt.algorithms.RSAAlgorithm.to_jwk(cls.key.public_key(), as_dict=True)
        cls.jwk.update(kid="test-key", use="sig", alg="RS256")

    def setUp(self):
        now = int(time.time())
        self.google = {
            "iss": "https://accounts.google.com", "aud": "google-test-client",
            "sub": "google-subject-123", "iat": now - 10, "exp": now + 120,
            "nonce": "server-transaction-nonce", "email": "teacher@example.com",
            "email_verified": True,
        }
        self.line = {
            "iss": "https://access.line.me", "aud": "line-test-channel",
            "sub": "U0123456789", "iat": now - 10, "exp": now + 120,
            "nonce": "server-transaction-nonce", "email": "hint@example.com",
        }
        self.requests = []

    def client(self, body=None, status=200, error=None):
        def handler(request):
            self.requests.append(request)
            self.assertEqual(request.extensions["timeout"]["read"], 5.0)
            if error:
                raise error
            return httpx.Response(status, json=body)
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    def token(self, claims=None, key=None, **headers):
        return jwt.encode(
            self.google if claims is None else claims, key or self.key,
            algorithm="RS256", headers={"kid": "test-key", **headers},
        )

    async def google_proof(self, claims=None, jwks=None, token=None, **kwargs):
        async with self.client({"keys": [self.jwk]} if jwks is None else jwks) as client:
            return await verify_google_id_token(
                token or self.token(claims), client_id="google-test-client",
                nonce="server-transaction-nonce", client=client, **kwargs,
            )

    async def line_proof(self, claims=None, *, liff=False):
        async with self.client(self.line if claims is None else claims) as client:
            args = dict(client_id="line-test-channel", provider_namespace="line-provider-A", client=client)
            if liff:
                return await verify_line_liff_token("test.line.token", **args)
            return await verify_line_oauth_token("test.line.token", nonce="server-transaction-nonce", **args)

    async def test_google_valid_signature_and_verified_attribute(self):
        proof = await self.google_proof()
        self.assertEqual((proof.provider, proof.issuer, proof.namespace, proof.subject),
                         ("google", "https://accounts.google.com", "global", self.google["sub"]))
        self.assertEqual(proof.verified_email, self.google["email"])
        self.assertEqual(str(self.requests[0].url), GOOGLE_JWKS_URL)
        self.assertEqual(self.requests[0].method, "GET")
        self.assertNotIn("authorization", self.requests[0].headers)

    async def test_google_canonicalizes_only_documented_issuer_alias(self):
        proof = await self.google_proof({**self.google, "iss": "accounts.google.com"})
        self.assertEqual(proof.issuer, "https://accounts.google.com")

    async def test_email_changes_do_not_change_google_subject_key(self):
        a = await self.google_proof()
        b = await self.google_proof({**self.google, "email": "changed@example.com"})
        self.assertEqual((a.issuer, a.namespace, a.subject), (b.issuer, b.namespace, b.subject))
        self.assertNotEqual(a.verified_email, b.verified_email)

    async def test_subject_and_email_are_not_in_debug_representation(self):
        proof = await self.google_proof()
        self.assertNotIn(self.google["sub"], repr(proof))
        self.assertNotIn(self.google["email"], repr(proof))

    async def test_google_claim_denials(self):
        changes = [
            {"aud": "other-client"}, {"iss": "https://attacker.example"},
            {"nonce": "another-browser"}, {"nonce": "\ud800"},
            {"exp": int(time.time()) - 1}, {"iat": int(time.time()) + 120},
            {"sub": ""}, {"sub": " "}, {"sub": 123}, {"sub": "x" * 256},
            {"email_verified": False}, {"email_verified": "true"}, {"email_verified": 1},
            {"email": "not-an-email"}, {"iat": True},
            {"azp": "other-client"}, {"aud": ["google-test-client", "other-client"]},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaisesRegex(ProviderProofError, "^invalid_provider_token$"):
                await self.google_proof({**self.google, **change})

    async def test_google_required_claims(self):
        for field in ["exp", "iat", "iss", "aud", "sub", "nonce", "email", "email_verified"]:
            claims = {k: v for k, v in self.google.items() if k != field}
            with self.subTest(field=field), self.assertRaises(ProviderProofError):
                await self.google_proof(claims)

    async def test_google_multiple_audiences_need_matching_authorized_party(self):
        proof = await self.google_proof({**self.google, "aud": ["google-test-client", "other"], "azp": "google-test-client"})
        self.assertEqual(proof.subject, self.google["sub"])

    async def test_wrong_signature(self):
        with self.assertRaisesRegex(ProviderProofError, "^invalid_provider_token$"):
            await self.google_proof(token=self.token(key=self.other_key))

    async def test_unknown_or_duplicate_key_id(self):
        for keys in [[], [{**self.jwk, "kid": "other"}], [self.jwk, self.jwk]]:
            with self.subTest(count=len(keys)), self.assertRaises(ProviderProofError):
                await self.google_proof(jwks={"keys": keys})

    async def test_wrong_key_algorithm_type_or_purpose(self):
        for change in [{"alg": "HS256"}, {"kty": "EC"}, {"use": "enc"}, {"key_ops": ["sign"]}]:
            with self.subTest(change=change), self.assertRaises(ProviderProofError):
                await self.google_proof(jwks={"keys": [{**self.jwk, **change}]})

    async def test_malformed_jwk(self):
        with self.assertRaises(ProviderProofError):
            await self.google_proof(jwks={"keys": [{"kid": "test-key", "kty": "RSA"}]})

    async def test_untrusted_key_url_is_never_fetched(self):
        await self.google_proof(token=self.token(jku="https://attacker.example/keys"))
        self.assertEqual([str(r.url) for r in self.requests], [GOOGLE_JWKS_URL])

    async def test_unsupported_critical_headers_rejected_before_network(self):
        with self.assertRaises(ProviderProofError):
            await self.google_proof(token=self.token(crit=["unimplemented-extension"]))
        self.assertEqual(self.requests, [])

    async def test_hmac_algorithm_rejected_before_network(self):
        token = jwt.encode(self.google, "test-only-key-which-is-not-an-rsa-key", algorithm="HS256", headers={"kid": "test-key"})
        with self.assertRaises(ProviderProofError):
            await self.google_proof(token=token)
        self.assertEqual(self.requests, [])

    async def test_google_nonce_cannot_be_omitted(self):
        async with self.client() as client:
            for nonce in [None, "", " "]:
                with self.subTest(nonce=nonce), self.assertRaises(ProviderProofError):
                    await verify_google_id_token(self.token(), client_id="google-test-client", nonce=nonce, client=client)
        self.assertEqual(self.requests, [])

    async def test_line_oauth_uses_fixed_verify_endpoint_and_nonce(self):
        proof = await self.line_proof()
        self.assertEqual((proof.provider, proof.namespace, proof.subject), ("line", "line-provider-A", self.line["sub"]))
        self.assertIsNone(proof.verified_email)
        request = self.requests[0]
        self.assertEqual(str(request.url), LINE_VERIFY_URL)
        self.assertEqual(request.method, "POST")
        self.assertEqual(parse_qs(request.content.decode()), {
            "id_token": ["test.line.token"], "client_id": ["line-test-channel"],
            "nonce": ["server-transaction-nonce"],
        })

    async def test_liff_verifies_server_side_without_invented_oauth_nonce(self):
        claims = {k: v for k, v in self.line.items() if k != "nonce"}
        proof = await self.line_proof(claims, liff=True)
        self.assertEqual(proof.subject, self.line["sub"])
        self.assertNotIn("nonce", parse_qs(self.requests[0].content.decode()))

    async def test_line_claim_denials(self):
        for change in [
            {"aud": "other-channel"}, {"iss": "https://attacker.example"},
            {"sub": ""}, {"sub": None}, {"exp": int(time.time()) - 1},
            {"iat": int(time.time()) + 120}, {"iat": "123"},
            {"nonce": "wrong-browser"}, {"nonce": None},
        ]:
            with self.subTest(change=change), self.assertRaises(ProviderProofError):
                await self.line_proof({**self.line, **change})

    async def test_line_required_claims(self):
        for field in ["iss", "aud", "sub", "exp", "iat", "nonce"]:
            with self.subTest(field=field), self.assertRaises(ProviderProofError):
                await self.line_proof({k: v for k, v in self.line.items() if k != field})

    async def test_liff_wrong_audience_still_fails(self):
        with self.assertRaises(ProviderProofError):
            await self.line_proof({**self.line, "aud": "other-channel"}, liff=True)

    async def test_line_namespace_is_explicit_not_guessed_from_channel(self):
        async with self.client(self.line) as client:
            with self.assertRaisesRegex(ProviderProofError, "^provider_not_configured$"):
                await verify_line_liff_token("test.line.token", client_id="line-test-channel", provider_namespace="", client=client)
        self.assertEqual(self.requests, [])

    async def test_line_oauth_cannot_use_liff_nonce_exemption(self):
        async with self.client(self.line) as client:
            with self.assertRaises(ProviderProofError):
                await verify_line_oauth_token("test.line.token", client_id="line-test-channel", provider_namespace="line-provider-A", nonce=None, client=client)
        self.assertEqual(self.requests, [])

    async def test_provider_failures_are_redacted(self):
        for status, expected in [(400, "invalid_provider_token"), (429, "provider_unavailable"), (500, "provider_unavailable"), (302, "provider_unavailable")]:
            async with self.client({"error": "sensitive-provider-response"}, status) as client:
                with self.subTest(status=status), self.assertRaisesRegex(ProviderProofError, "^" + expected + "$"):
                    await verify_line_liff_token("test.line.token", client_id="line-test-channel", provider_namespace="line-provider-A", client=client)
        self.assertEqual(len(self.requests), 4)

    async def test_timeout_is_redacted(self):
        async with self.client(error=httpx.ReadTimeout("sensitive-provider-response")) as client:
            with self.assertRaisesRegex(ProviderProofError, "^provider_unavailable$"):
                await verify_google_id_token(self.token(), client_id="google-test-client", nonce="server-transaction-nonce", client=client)

    async def test_oversized_and_nonobject_responses_fail_closed(self):
        for body in ["x" * (MAX_RESPONSE_BYTES + 1), [], {"keys": "wrong-type"}]:
            async with self.client(body) as client:
                with self.subTest(body_type=type(body).__name__), self.assertRaises(ProviderProofError):
                    await verify_google_id_token(self.token(), client_id="google-test-client", nonce="server-transaction-nonce", client=client)

    async def test_invalid_json_response_fails_closed(self):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="not JSON"))) as client:
            with self.assertRaisesRegex(ProviderProofError, "^provider_unavailable$"):
                await verify_line_liff_token("test.line.token", client_id="line-test-channel", provider_namespace="line-provider-A", client=client)

    async def test_reused_client_credentials_are_not_forwarded_to_provider(self):
        def handler(request):
            self.assertNotIn("authorization", request.headers)
            self.assertNotIn("cookie", request.headers)
            self.assertNotIn("x-internal-key", request.headers)
            return httpx.Response(200, json=self.line)
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            headers={"Authorization": "Bearer private-native-token", "X-Internal-Key": "private-key"},
            cookies={"LH_access": "private-native-cookie"}, auth=("private-user", "private-password"),
        ) as client:
            await verify_line_liff_token("test.line.token", client_id="line-test-channel", provider_namespace="line-provider-A", client=client)

    async def test_total_provider_deadline_is_bounded(self):
        async def handler(request):
            await asyncio.sleep(1)
            return httpx.Response(200, json=self.line)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch("src.services.auth.provider_proof.PROVIDER_TIMEOUT_SECONDS", 0.01):
                with self.assertRaisesRegex(ProviderProofError, "^provider_unavailable$"):
                    await verify_line_liff_token("test.line.token", client_id="line-test-channel", provider_namespace="line-provider-A", client=client)

    async def test_bad_token_inputs_make_no_network_request(self):
        for token in ["", None, "\ud800", "x" * (MAX_TOKEN_BYTES + 1)]:
            async with self.client(self.line) as client:
                with self.subTest(token_type=type(token).__name__), self.assertRaises(ProviderProofError):
                    await verify_line_liff_token(token, client_id="line-test-channel", provider_namespace="line-provider-A", client=client)
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()
