"""Stdlib-only contract tests; no network, credentials or running services."""
import asyncio
import base64
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from src.route66_ext.services.auth.oauth_transactions import COOKIE_NAME, CONSUME_SCRIPT, LinkActor, OAuthClient, OAuthTransactionError, OAuthTransactions, RedisTransactionStore, safe_return_path


class MemoryStore:
    def __init__(self):
        self.records = {}
        self.lock = asyncio.Lock()
        self.creates = 0
        self.ttls = []

    async def create(self, key, value, ttl):
        self.creates += 1
        self.ttls.append(ttl)
        async with self.lock:
            if key in self.records:
                return False
            self.records[key] = value
            return True

    async def consume(self, key, guard):
        async with self.lock:
            wire = self.records.get(key)
            if wire is None or json.loads(wire)["guard"] != guard:
                return None
            return self.records.pop(key)


class OAuthTransactionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = 1000
        self.store = MemoryStore()
        self.tx = OAuthTransactions(self.store, deployment="staging", secret=b"s" * 32, clock=lambda: self.now)
        self.google = OAuthClient("google", "google-test-client", "https://learn.example.com", "global")
        self.line = OAuthClient("line", "12345", "https://learn.example.com", "reviewed-line-provider")
        self.actor = LinkActor(10, "a" * 64)

    async def take(self, started, client=None, intent="signin", actor=None, **kw):
        return await self.tx.consume(client or self.google, intent=intent, state=started.state,
                                     browser_cookie=kw.get("cookie", started.browser_cookie), actor=actor)

    async def test_google_roundtrip_nonce_and_pkce(self):
        start = await self.tx.begin(self.google, intent="signin", return_path="/course/123?tab=lesson")
        query = parse_qs(urlsplit(start.authorization_url).query)
        result = await self.take(start)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(result.code_verifier.encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(query["nonce"], [result.nonce])
        self.assertEqual(query["code_challenge"], [challenge])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["prompt"], ["select_account"])
        self.assertEqual(query["redirect_uri"], ["https://learn.example.com/auth/callback/google"])
        self.assertEqual(result.return_path, "/course/123?tab=lesson")
        self.assertNotIn(result.code_verifier, start.authorization_url)
        self.assertEqual(self.store.ttls, [300])
        self.assertEqual(self.store.records, {})

    async def test_production_origin_is_configuration_not_staging_literal(self):
        prod = replace(self.google, public_origin="https://example.com")
        start = await self.tx.begin(prod, intent="signin")
        query = parse_qs(urlsplit(start.authorization_url).query)
        self.assertEqual(query["redirect_uri"], ["https://example.com/auth/callback/google"])
        await self.take(start, prod)

    async def test_line_requires_distinct_provider_endpoint(self):
        start = await self.tx.begin(self.line, intent="signin")
        self.assertTrue(start.authorization_url.startswith("https://access.line.me/oauth2/v2.1/authorize?"))
        result = await self.take(start, self.line)
        self.assertEqual(result.client.provider_namespace, "reviewed-line-provider")

    async def test_cookie_contract_and_no_sensitive_repr(self):
        start = await self.tx.begin(self.google, intent="signin")
        cookie = start.binding_cookie()
        self.assertEqual(cookie["key"], COOKIE_NAME)
        self.assertTrue(cookie["secure"] and cookie["httponly"])
        self.assertEqual(cookie["path"], "/")
        self.assertEqual(cookie["samesite"], "lax")
        self.assertNotIn("domain", cookie)
        self.assertNotIn(start.browser_cookie, json.dumps(start.public_response()))
        self.assertEqual(set(start.public_response()), {"url"})
        self.assertNotIn(start.browser_cookie, repr(start))
        self.assertNotIn(start.state, repr(start))
        self.assertNotIn(start.browser_cookie, str(self.store.records))
        self.assertNotIn(start.state, str(self.store.records))
        result = await self.take(start)
        self.assertNotIn(result.code_verifier, repr(result))
        self.assertNotIn(result.nonce, repr(result))

    async def test_existing_browser_cookie_supports_parallel_flows(self):
        a = await self.tx.begin(self.google, intent="signin")
        b = await self.tx.begin(self.line, intent="signin", browser_cookie=a.browser_cookie)
        self.assertNotEqual(a.state, b.state)
        await self.take(a)
        await self.take(b, self.line)

    async def test_replay_is_rejected(self):
        start = await self.tx.begin(self.google, intent="signin")
        await self.take(start)
        with self.assertRaisesRegex(OAuthTransactionError, "^invalid_oauth_transaction$"):
            await self.take(start)

    async def test_concurrent_callbacks_have_one_winner(self):
        start = await self.tx.begin(self.google, intent="signin")
        outcomes = await asyncio.gather(*(self.take(start) for _ in range(32)), return_exceptions=True)
        self.assertEqual(sum(not isinstance(r, Exception) for r in outcomes), 1)
        self.assertEqual(sum(isinstance(r, OAuthTransactionError) for r in outcomes), 31)

    async def test_wrong_browser_cannot_consume_legitimate_record(self):
        start = await self.tx.begin(self.google, intent="signin")
        with self.assertRaises(OAuthTransactionError):
            await self.take(start, cookie="b" * 43)
        await self.take(start)

    async def test_context_changes_rejected_without_consumption(self):
        for client in [replace(self.google, public_origin="https://example.com"),
                       replace(self.google, client_id="other-client"), self.line]:
            start = await self.tx.begin(self.google, intent="signin")
            with self.subTest(client=client), self.assertRaises(OAuthTransactionError):
                await self.take(start, client)
            await self.take(start)

    async def test_intent_cannot_change_at_callback(self):
        start = await self.tx.begin(self.google, intent="register")
        with self.assertRaises(OAuthTransactionError):
            await self.take(start)
        await self.take(start, intent="register")

    async def test_other_deployment_and_rotated_secret_cannot_consume(self):
        start = await self.tx.begin(self.google, intent="signin")
        for deployment, key in [("production", b"s" * 32), ("staging", b"t" * 32)]:
            other = OAuthTransactions(self.store, deployment=deployment, secret=key, clock=lambda: self.now)
            with self.assertRaises(OAuthTransactionError):
                await other.consume(self.google, intent="signin", state=start.state, browser_cookie=start.browser_cookie)
        await self.take(start)

    async def test_link_requires_same_native_actor_and_session(self):
        start = await self.tx.begin(self.line, intent="link", actor=self.actor)
        for actor in [LinkActor(11, "a" * 64), LinkActor(10, "b" * 64)]:
            with self.assertRaises(OAuthTransactionError):
                await self.take(start, self.line, intent="link", actor=actor)
        result = await self.take(start, self.line, intent="link", actor=self.actor)
        self.assertEqual(result.actor, self.actor)

    async def test_namespace_change_invalidates_line_transaction(self):
        start = await self.tx.begin(self.line, intent="signin")
        with self.assertRaises(OAuthTransactionError):
            await self.take(start, replace(self.line, provider_namespace="another-provider"))
        await self.take(start, self.line)

    async def test_invalid_intents_and_link_contexts_do_not_write(self):
        cases = [(self.line, "register", None), (self.line, "link", None),
                 (self.google, "signin", self.actor), (self.google, "merge", self.actor)]
        for client, intent, actor in cases:
            with self.subTest(intent=intent), self.assertRaises(OAuthTransactionError):
                await self.tx.begin(client, intent=intent, actor=actor)
        self.assertEqual(self.store.creates, 0)

    async def test_bad_state_or_browser_cookie_fails_closed(self):
        start = await self.tx.begin(self.google, intent="signin")
        for value in [None, "", "x" * 1000, "\r\n"]:
            with self.assertRaises(OAuthTransactionError):
                await self.take(start, cookie=value)
            with self.assertRaises(OAuthTransactionError):
                await self.tx.consume(self.google, intent="signin", state=value, browser_cookie=start.browser_cookie)
        await self.take(start)

    async def test_bad_browser_cookie_on_begin_never_writes(self):
        for cookie in ["", "wrong-cookie", 10]:
            with self.assertRaises(OAuthTransactionError):
                await self.tx.begin(self.google, intent="signin", browser_cookie=cookie)
        self.assertEqual(self.store.creates, 0)

    async def test_expiry_even_if_store_retains_old_snapshot(self):
        start = await self.tx.begin(self.google, intent="signin")
        self.now += 300
        with self.assertRaises(OAuthTransactionError):
            await self.take(start)
        self.assertEqual(self.store.records, {})

    async def test_future_transaction_clock_rejected(self):
        start = await self.tx.begin(self.google, intent="signin")
        self.now -= 1
        with self.assertRaises(OAuthTransactionError):
            await self.take(start)

    async def test_tampered_payload_is_authenticated_and_burned(self):
        start = await self.tx.begin(self.google, intent="signin")
        key = next(iter(self.store.records))
        wire = json.loads(self.store.records[key])
        payload = json.loads(wire["payload"])
        payload["return_path"] = "//attacker.example"
        wire["payload"] = json.dumps(payload)
        self.store.records[key] = json.dumps(wire)
        with self.assertRaises(OAuthTransactionError):
            await self.take(start)
        self.assertEqual(self.store.records, {})

    async def test_provider_failure_cannot_resurrect_consumed_transaction(self):
        start = await self.tx.begin(self.google, intent="signin")
        await self.take(start)  # Caller now attempts code redemption, which fails.
        with self.assertRaises(OAuthTransactionError):
            await self.take(start)
        fresh = await self.tx.begin(self.google, intent="signin", browser_cookie=start.browser_cookie)
        await self.take(fresh)

    async def test_store_failure_is_redacted_and_fails_closed(self):
        class BrokenStore:
            async def create(self, *args): raise RuntimeError("sensitive store details")
            async def consume(self, *args): raise RuntimeError("sensitive store details")
        tx = OAuthTransactions(BrokenStore(), deployment="staging", secret=b"s" * 32)
        with self.assertRaisesRegex(OAuthTransactionError, "^transaction_store_unavailable$"):
            await tx.begin(self.google, intent="signin")
        with self.assertRaisesRegex(OAuthTransactionError, "^transaction_store_unavailable$"):
            await tx.consume(self.google, intent="signin", state="a" * 43, browser_cookie="b" * 43)

    async def test_store_deadline_is_bounded(self):
        class SlowStore:
            async def create(self, *args): await asyncio.sleep(1)
        tx = OAuthTransactions(SlowStore(), deployment="staging", secret=b"s" * 32)
        with patch('src.route66_ext.services.auth.oauth_transactions.STORE_TIMEOUT_SECONDS', 0.01):
            with self.assertRaisesRegex(OAuthTransactionError, "^transaction_store_unavailable$"):
                await tx.begin(self.google, intent="signin")

    async def test_state_collisions_are_bounded_and_do_not_overwrite(self):
        class Collisions:
            def __init__(self): self.calls = 0
            async def create(self, *args): self.calls += 1; return False
        store = Collisions()
        tx = OAuthTransactions(store, deployment="staging", secret=b"s" * 32)
        with self.assertRaises(OAuthTransactionError):
            await tx.begin(self.google, intent="signin")
        self.assertEqual(store.calls, 3)

    async def test_redis_adapter_uses_nx_expiry_and_one_atomic_script(self):
        class Client:
            async def set(self, key, value, **kwargs):
                self.created = key, value, kwargs
                return True
            async def eval(self, script, n, key, guard):
                self.consumed = script, n, key, guard
                return b"record"
        client = Client()
        store = RedisTransactionStore(client)
        self.assertTrue(await store.create("key", "value", 300))
        self.assertEqual(client.created, ("key", "value", {"ex": 300, "nx": True}))
        self.assertEqual(await store.consume("key", "guard"), b"record")
        self.assertEqual(client.consumed, (CONSUME_SCRIPT, 1, "key", "guard"))


class OAuthConfigurationTests(unittest.TestCase):
    def test_rejects_noncanonical_or_unsafe_origin(self):
        for origin in ["http://learn.example.com", "https://user:pass@example.com", "https://example.com/",
                       "https://example.com:443", "https://example.com?x=1", "https://example.com#x",
                       "https://EXAMPLE.com", "https://bad_host.example", "//example.com", None]:
            with self.subTest(origin=origin), self.assertRaises(OAuthTransactionError):
                OAuthClient("google", "client", origin, "global")

    def test_provider_and_namespace_validation(self):
        for provider, namespace in [([], "global"), ("unknown", "global"),
                                    ("google", "another"), ("line", "x" * 129), ("line", "")]:
            with self.assertRaises(OAuthTransactionError):
                OAuthClient(provider, "client", "https://learn.example.com", namespace)

    def test_configuration_and_actor_validation(self):
        for kwargs in [dict(deployment="staging", secret=b"short"), dict(deployment="bad:namespace", secret=b"s"*32),
                       dict(deployment="staging", secret=b"s"*32, ttl=86400)]:
            with self.assertRaises(OAuthTransactionError): OAuthTransactions(MemoryStore(), **kwargs)
        for actor in [(0, "a"*64), (True, "a"*64), (1, "raw.native.session.token")]:
            with self.assertRaises(OAuthTransactionError): LinkActor(*actor)

    def test_safe_local_paths(self):
        for path in ["/", "/dash/courses", "/course/123?tab=lesson", "/course/%E0%B8%81"]:
            self.assertEqual(safe_return_path(path), path)

    def test_unsafe_or_encoded_redirects(self):
        for path in ["", "https://attacker.example", "//attacker.example", "/\\attacker.example", "/\n/evil",
                     "/%2fattacker.example", "/%252fattacker.example", "/%5cattacker.example", "/%0d%0aevil",
                     "/#fragment", "/%FF", "x"*3000, None]:
            with self.subTest(path=path), self.assertRaises(OAuthTransactionError): safe_return_path(path)


if __name__ == "__main__":
    unittest.main()

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
