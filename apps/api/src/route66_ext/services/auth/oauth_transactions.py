"""Browser-bound OAuth transactions; no account creation or session issuance.

Not connected to a route yet. Configuration and link actor/session context must
come from trusted server settings and verified native authentication, never JSON
fields supplied by a browser. Keep the binding cookie out of response bodies.

The Redis adapter atomically compares the context guard and deletes the record.
Use a dedicated deployment namespace/key, short TTLs, and a Redis client configured
with bounded socket/connect timeouts. Rotate the transaction key after restores;
never restore pending OAuth transactions into a new environment.
"""

import asyncio
import base64
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Callable, Protocol
from urllib.parse import unquote, urlencode, urlsplit

COOKIE_NAME = "__Host-LH_oauth_binding"
MAX_RECORD_BYTES = 32768
STORE_TIMEOUT_SECONDS = 3.0
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_NAME = re.compile(r"[A-Za-z0-9._:-]{1,255}\Z")
_SESSION = re.compile(r"[a-f0-9]{64}\Z")
_PROVIDERS = {
    "google": ("https://accounts.google.com/o/oauth2/v2/auth", "openid email profile"),
    "line": ("https://access.line.me/oauth2/v2.1/authorize", "openid profile"),
}

# A mismatch must not consume someone else's legitimate pending transaction.
# Comparison and deletion are ONE Redis operation, not a GET followed by DEL.
CONSUME_SCRIPT = """
local raw = redis.call('GET', KEYS[1])
if not raw or #raw > 32768 then return false end
local ok, record = pcall(cjson.decode, raw)
if not ok or type(record) ~= 'table' then return false end
if record.guard ~= ARGV[1] then return false end
redis.call('DEL', KEYS[1])
return raw
"""


class OAuthTransactionError(ValueError):
    """Redacted error code; never include state, cookies, tokens or payloads."""


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def safe_return_path(value: str) -> str:
    """Accept only a local path, rejecting encoded authority/control ambiguity."""
    if not isinstance(value, str) or not 0 < len(value) <= 2048:
        raise OAuthTransactionError("invalid_return_path")
    candidate = value
    for _ in range(5):
        if (
            not candidate.startswith("/") or candidate.startswith("//")
            or "\\" in candidate or any(ord(c) < 32 or ord(c) == 127 for c in candidate)
        ):
            raise OAuthTransactionError("invalid_return_path")
        try:
            parts = urlsplit(candidate)
            if parts.scheme or parts.netloc or parts.fragment:
                raise OAuthTransactionError("invalid_return_path")
            decoded = unquote(candidate, errors="strict")
        except (ValueError, UnicodeError):
            raise OAuthTransactionError("invalid_return_path") from None
        if decoded == candidate:
            return value
        candidate = decoded
    raise OAuthTransactionError("invalid_return_path")


@dataclass(frozen=True, slots=True)
class OAuthClient:
    provider: str
    client_id: str
    public_origin: str
    provider_namespace: str

    def __post_init__(self):
        try:
            parsed = urlsplit(self.public_origin)
            host = parsed.hostname or ""
            labels = host.split(".")
            valid_host = len(host) <= 253 and all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in labels
            )
        except (ValueError, TypeError, AttributeError):
            raise OAuthTransactionError("invalid_oauth_configuration") from None
        if (
            not isinstance(self.provider, str) or self.provider not in _PROVIDERS
            or not isinstance(self.client_id, str) or not _NAME.fullmatch(self.client_id)
            or not isinstance(self.provider_namespace, str) or len(self.provider_namespace) > 128
            or not _NAME.fullmatch(self.provider_namespace)
            or not valid_host or self.public_origin != "https://" + host
            or (self.provider == "google" and self.provider_namespace != "global")
        ):
            raise OAuthTransactionError("invalid_oauth_configuration")

    @property
    def callback_uri(self) -> str:
        # LINE path is reserved for upcoming route integration, not a live route.
        return self.public_origin + "/auth/callback/" + self.provider


@dataclass(frozen=True, slots=True)
class LinkActor:
    user_id: int
    session_fingerprint: str = field(repr=False)

    def __post_init__(self):
        if (
            type(self.user_id) is not int or self.user_id <= 0
            or not isinstance(self.session_fingerprint, str)
            or not _SESSION.fullmatch(self.session_fingerprint)
        ):
            raise OAuthTransactionError("invalid_link_context")


@dataclass(frozen=True, slots=True)
class StartedTransaction:
    authorization_url: str = field(repr=False)
    state: str = field(repr=False)
    browser_cookie: str = field(repr=False)
    expires_in: int

    def public_response(self) -> dict:
        return {"url": self.authorization_url}

    def binding_cookie(self) -> dict:
        """For the server Set-Cookie API only, NEVER a JSON response field."""
        return dict(key=COOKIE_NAME, value=self.browser_cookie, max_age=self.expires_in,
                    secure=True, httponly=True, samesite="lax", path="/")


@dataclass(frozen=True, slots=True)
class ConsumedTransaction:
    client: OAuthClient
    intent: str
    return_path: str
    nonce: str = field(repr=False)
    code_verifier: str = field(repr=False)
    actor: LinkActor | None = field(repr=False)


class TransactionStore(Protocol):
    async def create(self, key: str, value: str, ttl: int) -> bool: ...
    async def consume(self, key: str, guard: str) -> str | bytes | None: ...


class RedisTransactionStore:
    """Accepts redis.asyncio.Redis; no connection or writes during import."""

    def __init__(self, client):
        self.client = client

    async def create(self, key: str, value: str, ttl: int) -> bool:
        return bool(await self.client.set(key, value, ex=ttl, nx=True))

    async def consume(self, key: str, guard: str) -> str | bytes | None:
        return await self.client.eval(CONSUME_SCRIPT, 1, key, guard)


class OAuthTransactions:
    def __init__(
        self, store: TransactionStore, *, deployment: str, secret: bytes,
        ttl: int = 300, clock: Callable[[], float] = time.time,
    ):
        if (
            not isinstance(deployment, str) or not re.fullmatch(r"[a-z0-9_-]{1,64}", deployment)
            or not isinstance(secret, bytes) or len(secret) < 32
            or type(ttl) is not int or not 60 <= ttl <= 600
        ):
            raise OAuthTransactionError("invalid_oauth_configuration")
        self.store, self.deployment, self.secret, self.ttl, self.clock = store, deployment, secret, ttl, clock

    def _mac(self, purpose: str, value: str) -> str:
        return hmac.new(self.secret, (purpose + "\0" + value).encode(), hashlib.sha256).hexdigest()

    def _key(self, state: str) -> str:
        return "lh:oauth:v1:" + self.deployment + ":" + hashlib.sha256(state.encode()).hexdigest()

    def _guard(self, client: OAuthClient, intent: str, state: str, cookie: str, actor: LinkActor | None) -> str:
        return self._mac("context", _json({
            "deployment": self.deployment, "provider": client.provider,
            "namespace": client.provider_namespace, "client_id": client.client_id,
            "callback": client.callback_uri, "intent": intent, "state": state,
            "browser": cookie, "actor": actor.user_id if actor else None,
            "session": actor.session_fingerprint if actor else None,
        }))

    @staticmethod
    def _intent(client: OAuthClient, intent: str, actor: LinkActor | None):
        if intent not in ("signin", "register", "link") or ((intent == "link") != (actor is not None)):
            raise OAuthTransactionError("invalid_oauth_intent")
        if client.provider == "line" and intent == "register":
            raise OAuthTransactionError("line_registration_forbidden")
        if actor is not None and not isinstance(actor, LinkActor):
            raise OAuthTransactionError("invalid_link_context")

    async def begin(
        self, client: OAuthClient, *, intent: str, return_path: str = "/",
        browser_cookie: str | None = None, actor: LinkActor | None = None,
    ) -> StartedTransaction:
        self._intent(client, intent, actor)
        safe_return_path(return_path)
        cookie = secrets.token_urlsafe(32) if browser_cookie is None else browser_cookie
        if not isinstance(cookie, str) or not _TOKEN.fullmatch(cookie):
            raise OAuthTransactionError("invalid_browser_binding")
        nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
        now = int(self.clock())
        payload = _json({"created_at": now, "expires_at": now + self.ttl,
                         "return_path": return_path, "nonce": nonce, "code_verifier": verifier})
        for _ in range(3):
            state = secrets.token_urlsafe(32)
            guard = self._guard(client, intent, state, cookie, actor)
            # Authenticate the context AND the complete stored payload.
            wire = _json({"guard": guard, "payload": payload,
                          "mac": self._mac("record", guard + "\0" + payload)})
            try:
                async with asyncio.timeout(STORE_TIMEOUT_SECONDS):
                    created = await self.store.create(self._key(state), wire, self.ttl)
            except Exception:
                raise OAuthTransactionError("transaction_store_unavailable") from None
            if created:
                challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
                endpoint, scope = _PROVIDERS[client.provider]
                parameters = dict(
                    client_id=client.client_id, redirect_uri=client.callback_uri,
                    response_type="code", scope=scope, state=state, nonce=nonce,
                    code_challenge=challenge, code_challenge_method="S256",
                )
                if client.provider == "google":
                    parameters["prompt"] = "select_account"
                url = endpoint + "?" + urlencode(parameters)
                return StartedTransaction(url, state, cookie, self.ttl)
        raise OAuthTransactionError("transaction_store_unavailable")

    async def consume(
        self, client: OAuthClient, *, intent: str, state: str,
        browser_cookie: str, actor: LinkActor | None = None,
    ) -> ConsumedTransaction:
        """Consume BEFORE code redemption, including cancellation/error callbacks.

        A provider failure never resurrects this record. An ambiguous cache/network
        failure also fails closed; start a new flow, do not exchange the code.
        """
        self._intent(client, intent, actor)
        if any(not isinstance(v, str) or not _TOKEN.fullmatch(v) for v in (state, browser_cookie)):
            raise OAuthTransactionError("invalid_oauth_transaction")
        guard = self._guard(client, intent, state, browser_cookie, actor)
        try:
            async with asyncio.timeout(STORE_TIMEOUT_SECONDS):
                raw = await self.store.consume(self._key(state), guard)
        except Exception:
            raise OAuthTransactionError("transaction_store_unavailable") from None
        try:
            if not isinstance(raw, (str, bytes)) or len(raw) > MAX_RECORD_BYTES:
                raise ValueError()
            record = json.loads(raw)
            payload = record["payload"]
            if not isinstance(payload, str) or not hmac.compare_digest(
                record["mac"], self._mac("record", guard + "\0" + payload)
            ):
                raise ValueError()
            data = json.loads(payload)
            now = self.clock()
            if (
                type(data["created_at"]) is not int or type(data["expires_at"]) is not int
                or not data["created_at"] <= now < data["expires_at"]
                or not 0 < data["expires_at"] - data["created_at"] <= self.ttl
                or not isinstance(data["nonce"], str) or not _TOKEN.fullmatch(data["nonce"])
                or not isinstance(data["code_verifier"], str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{86}", data["code_verifier"])
            ):
                raise ValueError()
            return ConsumedTransaction(client, intent, safe_return_path(data["return_path"]),
                                       data["nonce"], data["code_verifier"], actor)
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError):
            raise OAuthTransactionError("invalid_oauth_transaction") from None

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
