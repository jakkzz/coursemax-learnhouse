"""Transient storage contract; Redis integration uses a disposable Unix socket."""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
import time
import unittest
from uuid import uuid4
from src.route66_ext.services.attendance_handoff import CLAIM, Handoffs, Reservation, RETENTION_SECONDS


class MemoryRedis:
    def __init__(self): self.data = {}
    async def set(self, key, value, *, nx=False, ex=None):
        if nx and await self.get(key) is not None: return False
        self.data[key] = (value, time.monotonic() + ex)
        return True
    async def get(self, key):
        value, end = self.data.get(key, (None, 0))
        return value if end > time.monotonic() else None
    async def eval(self, script, count, key, actor):
        assert script == CLAIM and count == 1
        raw = await self.get(key)
        if raw is None: return None
        value = json.loads(raw)
        if value['owner'] not in (0, actor): return None
        value['owner'] = actor
        raw = json.dumps(value)
        self.data[key] = (raw, self.data[key][1])
        return raw
    async def pttl(self, key):
        return max(-2, int((self.data.get(key, ('', 0))[1] - time.monotonic()) * 1000))


class HandoffTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.redis = MemoryRedis()
        self.store = Handoffs(self.redis, 'synthetic-' + uuid4().hex)
        now = datetime.now(timezone.utc)
        self.record = Reservation(10, 20, 0, now, now + timedelta(minutes=10))

    async def test_roundtrip_and_bounded_retention(self):
        handle = await self.store.create(self.record)
        self.assertRegex(handle, r'^[A-Za-z0-9_-]{43}$')
        self.assertNotIn(handle, self.store.key(handle))
        self.assertEqual(await self.store.get(handle), self.record)
        ttl = await self.redis.pttl(self.store.key(handle))
        self.assertGreater(ttl, 1190000)
        self.assertLessEqual(ttl, RETENTION_SECONDS * 1000)
        with self.assertRaises(ValueError): await Handoffs(self.redis, 'other').get(handle)

    async def test_concurrent_claim_has_one_owner_and_keeps_ttl(self):
        handle = await self.store.create(self.record)
        before = await self.redis.pttl(self.store.key(handle))
        results = await asyncio.gather(*(self.store.claim(handle, actor) for actor in range(1, 33)), return_exceptions=True)
        claimed = [item for item in results if isinstance(item, Reservation)]
        self.assertEqual(len(claimed), 1)
        self.assertEqual(await self.store.claim(handle, claimed[0].owner), claimed[0])
        self.assertLessEqual(await self.redis.pttl(self.store.key(handle)), before)
        with self.assertRaises(ValueError): await self.store.claim(handle, claimed[0].owner + 100)

    async def test_completed_retry_metadata_outlives_usable_window(self):
        old = replace(self.record, arrived_at=self.record.arrived_at-timedelta(minutes=11), expires_at=self.record.expires_at-timedelta(minutes=11))
        handle = await self.store.create(old)
        self.assertLess(old.expires_at, datetime.now(timezone.utc))
        self.assertEqual((await self.store.claim(handle, 7)).arrived_at, old.arrived_at)
        # Persistence, not this cache, decides whether an old committed receipt exists.
        self.assertEqual((await self.store.get(handle)).owner, 7)

    async def test_missing_and_malformed_records_fail_closed(self):
        with self.assertRaises(ValueError): await self.store.get('missing')
        wire = json.loads(self.record.wire())
        for patch in ({'owner': True}, {'challenge_id': 0}, {'session_version': -1}, {'arrived_at': '2026-10-17T00:00:00'}, {'expires_at': (self.record.arrived_at+timedelta(hours=1)).isoformat()}, {'extra': 1}):
            with self.subTest(patch=patch), self.assertRaises(ValueError): Reservation.read(json.dumps({**wire, **patch}))


@unittest.skipUnless(os.getenv('RUN_OAUTH_REDIS_TESTS') == '1', 'disposable Redis only')
class RealRedisHandoffTests(HandoffTests):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        from redis.asyncio import Redis
        self.redis = Redis(unix_socket_path=os.environ['OAUTH_TEST_REDIS_SOCKET'])
        self.store = Handoffs(self.redis, 'synthetic-' + uuid4().hex)
    async def asyncTearDown(self):
        await self.redis.aclose()
