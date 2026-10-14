"""Server-side provider proof, not account resolution or session issuance.

Google's native login route first consumes a browser-bound, server-created OAuth
transaction; its nonce is NOT a client-supplied claim. LINE primitives remain
unactivated. Optional profile attributes are captured only after verification.
Google/LINE subjects subsequently require persisted ownership checks. In
particular, verified LINE proof does not authorize registration or linking.

Provider URLs are fixed, redirects disabled, requests bounded, and errors contain
no tokens, subjects, email addresses or provider response bodies. No provider
credentials or tokens are retained by this module.
"""

import asyncio
from dataclasses import dataclass, field
import hmac
import json
import time
from typing import Literal

import httpx
import jwt
from pydantic import EmailStr, TypeAdapter, ValidationError
from src.services.auth.provider_profile import ProviderProfile, extract_profile

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
LINE_VERIFY_URL = "https://api.line.me/oauth2/v2.1/verify"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
LINE_ISSUER = "https://access.line.me"
MAX_RESPONSE_BYTES = 64 * 1024
MAX_TOKEN_BYTES = 16 * 1024
PROVIDER_TIMEOUT_SECONDS = 5.0
_EMAIL = TypeAdapter(EmailStr)


class ProviderProofError(ValueError):
    """Stable, non-sensitive failure codes suitable for an API boundary."""


@dataclass(frozen=True, slots=True)
class ProviderProof:
    provider: Literal["google", "line"]
    issuer: str
    namespace: str
    subject: str = field(repr=False)
    verified_email: str | None = field(default=None, repr=False)
    profile: ProviderProfile | None = field(default=None, repr=False)
    expires_at: int | None = field(default=None, repr=False, compare=False)
    hosted_domain: str | None = field(default=None, repr=False, compare=False)


def _opaque(value: object, maximum: int = 255) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= maximum
        and value.isascii()
        and value.isprintable()
        and value == value.strip()
    )


def _inputs(token: str, client_id: str, nonce: str | None) -> None:
    if not _opaque(client_id) or (nonce is not None and not _opaque(nonce, 256)):
        raise ProviderProofError("provider_not_configured")
    if not isinstance(token, str) or not token or not token.isascii() or len(token) > MAX_TOKEN_BYTES:
        raise ProviderProofError("invalid_provider_token")


async def _json_response(
    client: httpx.AsyncClient, method: str, url: str, *, data: dict | None = None
) -> dict:
    # Build an independent request: never forward a reused client's native auth,
    # cookies or internal-service headers to a provider. Reuse only its transport.
    request = httpx.Request(
        method, url, data=data, headers={"Accept": "application/json"},
        extensions={"timeout": dict.fromkeys(
            ("connect", "read", "write", "pool"), PROVIDER_TIMEOUT_SECONDS
        )},
    )
    try:
        # A read timeout alone does not bound a slow trickle of response bytes.
        async with asyncio.timeout(PROVIDER_TIMEOUT_SECONDS):
            response = await client.send(request, stream=True, auth=None, follow_redirects=False)
            try:
                if response.status_code != 200:
                    if url == LINE_VERIFY_URL and 400 <= response.status_code < 500 and response.status_code != 429:
                        raise ProviderProofError("invalid_provider_token")
                    raise ProviderProofError("provider_unavailable")
                chunks = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    if len(chunks) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise ProviderProofError("provider_unavailable")
                    chunks.extend(chunk)
            finally:
                await response.aclose()
    except (httpx.HTTPError, TimeoutError):
        raise ProviderProofError("provider_unavailable") from None
    try:
        value = json.loads(chunks)
    except (ValueError, UnicodeError, RecursionError):
        raise ProviderProofError("provider_unavailable") from None
    if not isinstance(value, dict):
        raise ProviderProofError("provider_unavailable")
    return value


def _claims(claims: dict, nonce: str | None) -> str:
    now = time.time()
    # bool is an int subclass; neither booleans nor numeric strings are dates.
    if (
        type(claims.get("exp")) is not int
        or type(claims.get("iat")) is not int
        or claims["exp"] <= now
        or claims["iat"] > now
        or claims["iat"] >= claims["exp"]
        or not _opaque(claims.get("sub"))
    ):
        raise ProviderProofError("invalid_provider_token")
    if nonce is not None:
        actual = claims.get("nonce")
        if not _opaque(actual, 256) or not hmac.compare_digest(actual, nonce):
            raise ProviderProofError("invalid_provider_token")
    return claims["sub"]


async def verify_google_id_token(
    token: str, *, client_id: str, nonce: str, client: httpx.AsyncClient
) -> ProviderProof:
    """Verify Google's signed ID token using its fixed public-key endpoint.

    Email is an attribute, never an account lookup key. Google subjects use the
    canonical issuer/global namespace, not the OAuth client ID as a new identity.
    """
    if nonce is None:
        raise ProviderProofError("provider_not_configured")
    _inputs(token, client_id, nonce)
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise ProviderProofError("invalid_provider_token") from None
    if (
        header.get("alg") != "RS256"
        or not _opaque(header.get("kid"), 128)
        or "crit" in header
        or "b64" in header
    ):
        raise ProviderProofError("invalid_provider_token")
    keys = (await _json_response(client, "GET", GOOGLE_JWKS_URL)).get("keys")
    if not isinstance(keys, list):
        raise ProviderProofError("provider_unavailable")
    matching = [key for key in keys if isinstance(key, dict) and key.get("kid") == header["kid"]]
    if len(matching) != 1:
        raise ProviderProofError("invalid_provider_token")
    key = matching[0]
    if (
        key.get("kty") != "RSA"
        or key.get("alg", "RS256") != "RS256"
        or key.get("use", "sig") != "sig"
        or ("key_ops" in key and key["key_ops"] != ["verify"])
    ):
        raise ProviderProofError("invalid_provider_token")
    try:
        signing_key = jwt.PyJWK.from_dict(key, algorithm="RS256").key
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=GOOGLE_ISSUERS,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
        )
    except (jwt.PyJWTError, ValueError, TypeError):
        raise ProviderProofError("invalid_provider_token") from None
    audience = claims["aud"]
    if (
        (isinstance(audience, list) and len(audience) > 1 and claims.get("azp") != client_id)
        or ("azp" in claims and claims["azp"] != client_id)
        or claims.get("email_verified") is not True
    ):
        raise ProviderProofError("invalid_provider_token")
    subject = _claims(claims, nonce)
    try:
        email = str(_EMAIL.validate_python(claims.get("email")))
    except ValidationError:
        raise ProviderProofError("invalid_provider_token") from None
    return ProviderProof("google", GOOGLE_ISSUERS[0], "global", subject, email,
                         extract_profile('google', claims),
                         hosted_domain=claims.get('hd') if _opaque(claims.get('hd')) else None)


async def _verify_line(
    token: str, *, client_id: str, provider_namespace: str,
    nonce: str | None, client: httpx.AsyncClient,
) -> ProviderProof:
    _inputs(token, client_id, nonce)
    # LINE user IDs are provider-scoped. This is a reviewed server configuration
    # value, never a namespace inferred from a browser claim or a new channel ID.
    if not _opaque(provider_namespace, 128):
        raise ProviderProofError("provider_not_configured")
    data = {"id_token": token, "client_id": client_id}
    if nonce is not None:
        data["nonce"] = nonce
    claims = await _json_response(client, "POST", LINE_VERIFY_URL, data=data)
    if claims.get("iss") != LINE_ISSUER or claims.get("aud") != client_id:
        raise ProviderProofError("invalid_provider_token")
    subject = _claims(claims, nonce)
    # LINE email, if supplied, is not proof of our Google verified-email policy.
    return ProviderProof("line", LINE_ISSUER, provider_namespace, subject,
                         profile=extract_profile('line', claims), expires_at=claims['exp'])


async def verify_line_oauth_token(
    token: str, *, client_id: str, provider_namespace: str,
    nonce: str, client: httpx.AsyncClient,
) -> ProviderProof:
    if nonce is None:
        raise ProviderProofError("provider_not_configured")
    return await _verify_line(
        token, client_id=client_id, provider_namespace=provider_namespace,
        nonce=nonce, client=client,
    )


async def verify_line_liff_token(
    token: str, *, client_id: str, provider_namespace: str, client: httpx.AsyncClient,
) -> ProviderProof:
    """LIFF has no app-created OAuth nonce; always ask LINE to verify the token.

    The eventual session endpoint must allow only already-bound, active accounts.
    This function alone never creates, links, merges or signs in any account.
    """
    return await _verify_line(
        token, client_id=client_id, provider_namespace=provider_namespace,
        nonce=None, client=client,
    )
