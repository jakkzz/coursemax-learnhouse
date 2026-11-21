"""One in-process coordinator, deployment Redis leadership and SQL fencing."""
import asyncio
from contextlib import asynccontextmanager, suppress
import logging
import os
from uuid import uuid4

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from src.route66_ext.adapters.config_config import get_learnhouse_config
from src.route66_ext.services import roster_refresh as service

log = logging.getLogger(__name__)
RENEW = "if redis.call('GET',KEYS[1]) == ARGV[1] then return redis.call('EXPIRE',KEYS[1],60) end; return 0"
RELEASE = "if redis.call('GET',KEYS[1]) == ARGV[1] then return redis.call('DEL',KEYS[1]) end; return 0"


async def tick(sessions, redis, key, token, org_id):
    # A failed renewal never permits another SQL claim or source request.
    leader = await redis.eval(RENEW, 1, key, token)
    if not leader:
        leader = await redis.set(key, token, nx=True, ex=60)
    if not leader:
        return False
    await service.initialise(sessions, org_id)
    if not await redis.eval(RENEW, 1, key, token):
        return False
    claim = await service.claim_one(sessions, org_id)
    if claim and await redis.eval(RENEW, 1, key, token):
        await service.run_one(sessions, org_id, claim)
    return bool(claim)


async def run(sessions):
    token = uuid4().hex
    redis = None
    key = None
    try:
        while True:
            try:
                org_id = int(os.environ['LEARNHOUSE_GOOGLE_ORG_ID'])
                if org_id <= 0:
                    raise ValueError('Unconfigured organization')
                if redis is None:
                    connection = get_learnhouse_config().redis_config.redis_connection_string
                    if not connection:
                        raise ValueError('Unconfigured Redis')
                    redis = Redis.from_url(connection, socket_timeout=3, socket_connect_timeout=3)
                    key = 'lh:roster-refresh:' + os.environ['LEARNHOUSE_OAUTH_DEPLOYMENT']
                worked = await tick(sessions, redis, key, token, org_id)
                await asyncio.sleep(2 if worked else 15)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning('Roster refresh will retry (%s); saved memberships unchanged', type(exc).__name__)
                await asyncio.sleep(60)
    finally:
        if redis is not None:
            with suppress(Exception):
                if key:
                    await redis.eval(RELEASE, 1, key, token)
            await redis.aclose()


@asynccontextmanager
async def lifespan(app):
    # Native startup runs before this composed router lifespan; never add a pool.
    from src.route66_ext.adapters.core_events_database import engine
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    task = asyncio.create_task(run(sessions), name='route66-roster-refresh')
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
