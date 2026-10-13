"""Opt-in tests against a disposable Unix-socket Redis, never the app cache.

Use deploy/staging/test_oauth_redis.sh. Keys are independently namespaced and only
that namespace is cleaned up; no FLUSHDB/FLUSHALL or database switching is used.
"""
import asyncio
from dataclasses import replace
import json
import os
import unittest
import uuid

from src.services.auth.oauth_transactions import (
    LinkActor, OAuthClient, OAuthTransactionError, OAuthTransactions,
    RedisTransactionStore,
)


@unittest.skipUnless(os.getenv("RUN_OAUTH_REDIS_TESTS") == "1", "requires isolated Redis fixture")
class RedisOAuthTransactionsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from redis.asyncio import Redis
        socket = os.environ["OAUTH_TEST_REDIS_SOCKET"]
        if socket != "/scratch/redis.sock":
            raise RuntimeError("Use the dedicated test harness socket")
        self.redis = Redis(unix_socket_path=socket, socket_connect_timeout=2, socket_timeout=2)
        await self.redis.ping()
        self.deployment = "test-" + uuid.uuid4().hex
        self.prefix = "lh:oauth:v1:" + self.deployment + ":"
        self.tx = OAuthTransactions(RedisTransactionStore(self.redis), deployment=self.deployment, secret=b"test-key" * 4)
        self.client = OAuthClient("google", "test-client", "https://learn.example.com", "global")

    async def asyncTearDown(self):
        keys = [key async for key in self.redis.scan_iter(match=self.prefix + "*")]
        if keys:
            await self.redis.delete(*keys)
        await self.redis.aclose()

    async def take(self, start, *, client=None, actor=None, intent="signin", cookie=None):
        return await self.tx.consume(client or self.client, intent=intent, state=start.state,
                                     browser_cookie=cookie or start.browser_cookie, actor=actor)

    async def test_real_expiry_nx_and_round_trip(self):
        start = await self.tx.begin(self.client, intent="signin")
        key = self.tx._key(start.state)
        raw = await self.redis.get(key)
        self.assertGreater(await self.redis.ttl(key), 0)
        self.assertLessEqual(await self.redis.ttl(key), 300)
        self.assertFalse(await self.tx.store.create(key, "replacement", 300))
        self.assertEqual(await self.redis.get(key), raw)
        result = await self.take(start)
        self.assertEqual(result.client, self.client)
        self.assertEqual(await self.redis.exists(key), 0)

    async def test_32_simultaneous_callbacks_have_exactly_one_winner(self):
        start = await self.tx.begin(self.client, intent="signin")
        results = await asyncio.gather(*(self.take(start) for _ in range(32)), return_exceptions=True)
        self.assertEqual(sum(not isinstance(x, Exception) for x in results), 1)
        self.assertEqual(sum(isinstance(x, OAuthTransactionError) for x in results), 31)

    async def test_cross_browser_and_origin_do_not_burn_valid_transaction(self):
        start = await self.tx.begin(self.client, intent="signin")
        with self.assertRaises(OAuthTransactionError):
            await self.take(start, cookie="x" * 43)
        with self.assertRaises(OAuthTransactionError):
            await self.take(start, client=replace(self.client, public_origin="https://example.com"))
        self.assertEqual(await self.redis.exists(self.tx._key(start.state)), 1)
        await self.take(start)

    async def test_link_context_enforced_by_real_script(self):
        actor = LinkActor(10, "a" * 64)
        start = await self.tx.begin(self.client, intent="link", actor=actor)
        with self.assertRaises(OAuthTransactionError):
            await self.take(start, intent="link", actor=LinkActor(11, "a" * 64))
        with self.assertRaises(OAuthTransactionError):
            await self.take(start, intent="link", actor=LinkActor(10, "b" * 64))
        await self.take(start, intent="link", actor=actor)

    async def test_redis_ttl_expiration_rejects_callback(self):
        start = await self.tx.begin(self.client, intent="signin")
        await self.redis.pexpire(self.tx._key(start.state), 20)
        await asyncio.sleep(0.06)
        with self.assertRaises(OAuthTransactionError):
            await self.take(start)

    async def test_malformed_or_oversized_record_fails_closed(self):
        for value in ("not-json", "[]", "x" * 32769):
            start = await self.tx.begin(self.client, intent="signin")
            key = self.tx._key(start.state)
            await self.redis.set(key, value, ex=30)
            with self.subTest(value_length=len(value)), self.assertRaises(OAuthTransactionError):
                await self.take(start)

    async def test_payload_tampering_rejected_after_atomic_take(self):
        start = await self.tx.begin(self.client, intent="signin")
        key = self.tx._key(start.state)
        record = json.loads(await self.redis.get(key))
        record["payload"] = record["payload"].replace('"return_path":"/"', '"return_path":"//attacker.example"')
        await self.redis.set(key, json.dumps(record), ex=30)
        with self.assertRaises(OAuthTransactionError):
            await self.take(start)
        self.assertEqual(await self.redis.exists(key), 0)

    async def test_provider_failure_does_not_restore_consumed_record(self):
        start = await self.tx.begin(self.client, intent="signin")
        await self.take(start)
        # A provider failure occurs after this point. A retry cannot reuse state.
        with self.assertRaises(OAuthTransactionError):
            await self.take(start)

    async def test_independent_deployment_cannot_consume_staging_state(self):
        start = await self.tx.begin(self.client, intent="signin")
        other = OAuthTransactions(self.tx.store, deployment="other-" + uuid.uuid4().hex, secret=b"test-key" * 4)
        with self.assertRaises(OAuthTransactionError):
            await other.consume(self.client, intent="signin", state=start.state, browser_cookie=start.browser_cookie)
        await self.take(start)


if __name__ == "__main__":
    unittest.main()
