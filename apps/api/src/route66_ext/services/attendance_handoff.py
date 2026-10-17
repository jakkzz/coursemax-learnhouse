"""Transient scan continuation. The immutable SQL receipt remains authoritative."""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
import secrets

HANDOFF_WINDOW = timedelta(minutes=10)
# Keep ownership after the usable window for receipt retries/lost acknowledgements.
RETENTION_SECONDS = 20 * 60
CLAIM = """
local raw = redis.call('GET', KEYS[1])
if not raw then return false end
local record = cjson.decode(raw)
local actor = tonumber(ARGV[1])
if record.owner ~= 0 and record.owner ~= actor then return false end
record.owner = actor
local claimed = cjson.encode(record)
redis.call('SET', KEYS[1], claimed, 'KEEPTTL')
return claimed
"""


@dataclass(frozen=True)
class Reservation:
    challenge_id: int
    session_id: int
    session_version: int
    arrived_at: datetime
    expires_at: datetime
    owner: int = 0

    def wire(self):
        return json.dumps({**asdict(self), 'arrived_at': self.arrived_at.isoformat(), 'expires_at': self.expires_at.isoformat()})

    @classmethod
    def read(cls, raw):
        try:
            data = json.loads(raw)
            for key in ('challenge_id', 'session_id', 'session_version', 'owner'):
                if type(data[key]) is not int or data[key] < (1 if key.endswith('_id') else 0):
                    raise ValueError()
            for key in ('arrived_at', 'expires_at'):
                data[key] = datetime.fromisoformat(data[key])
                if data[key].tzinfo is None:
                    raise ValueError()
            record = cls(**data)
            if not record.arrived_at < record.expires_at <= record.arrived_at + HANDOFF_WINDOW:
                raise ValueError()
            return record
        except (ValueError, TypeError, KeyError, OverflowError):
            raise ValueError('handoff_expired') from None


class Handoffs:
    def __init__(self, redis, deployment):
        self.redis, self.prefix = redis, 'lh:attendance-handoff:' + deployment + ':'

    def key(self, handle):
        return self.prefix + sha256(handle.encode()).hexdigest()

    async def create(self, record):
        for _ in range(3):
            handle = secrets.token_urlsafe(32)
            if await self.redis.set(self.key(handle), record.wire(), nx=True, ex=RETENTION_SECONDS):
                return handle
        raise RuntimeError('handoff_unavailable')

    async def get(self, handle):
        raw = await self.redis.get(self.key(handle))
        if not raw:
            raise ValueError('handoff_expired')
        return Reservation.read(raw)

    async def claim(self, handle, actor):
        raw = await self.redis.eval(CLAIM, 1, self.key(handle), actor)
        if not raw:
            raise ValueError('handoff_claimed_or_expired')
        return Reservation.read(raw)
