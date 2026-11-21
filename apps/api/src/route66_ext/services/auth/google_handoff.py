"""Google code exchange: server-only verified result, no tokens to browser.

Joins tested OAuthTransactions and provider_proof primitives with bounded code
redemption. Consumes transaction FIRST, including on error. Returns only verified
proof, intent, return path and actor; never exposes access/refresh tokens.

This is internal server data, NOT a JSON response or permission to issue a session.
Callers must enforce native identity ownership, account/session lifecycle, MFA and
organization admission. Signin must never silently fall back to registration.
Link actors must come from a currently verified native session, not browser input.
Public/allowlist registration policy is admission only, never an identity/merge or role key.
"""

import asyncio
from dataclasses import dataclass, field

import httpx
from pydantic import TypeAdapter, EmailStr, ValidationError

from src.route66_ext.services.auth.oauth_transactions import OAuthClient, OAuthTransactions, OAuthTransactionError, LinkActor
from src.route66_ext.services.auth.provider_proof import ProviderProof, ProviderProofError, verify_google_id_token, _json_response, MAX_TOKEN_BYTES


GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
HANDOFF_TIMEOUT_SECONDS = 10.0
_EMAIL = TypeAdapter(EmailStr)


class GoogleHandoffError(ValueError):
    """Redacted error; never includes code, nonce, verifier, secret or subject."""


@dataclass(frozen=True, slots=True)
class GoogleHandoffConfig:
    """Google OAuth configuration for code exchange and registration admission.

    client_secret and registration_emails are never exposed in repr or errors.
    """
    client: OAuthClient
    client_secret: str = field(repr=False)
    registration_emails: frozenset[str] = field(default_factory=frozenset, repr=False)
    public_registration: bool = False

    @property
    def registration_enabled(self):
        return self.public_registration or bool(self.registration_emails)

    def __post_init__(self):
        if (
            not isinstance(self.client, OAuthClient)
            or self.client.provider != "google"
            or self.client.provider_namespace != "global"
        ):
            raise GoogleHandoffError("invalid_google_configuration")

        if (
            not isinstance(self.client_secret, str)
            or not self.client_secret
            or self.client_secret != self.client_secret.strip()
            or not self.client_secret.isascii()
            or not all(c.isprintable() for c in self.client_secret)
            or len(self.client_secret) > 255
        ):
            raise GoogleHandoffError("invalid_google_configuration")

        if type(self.public_registration) is not bool:
            raise GoogleHandoffError("invalid_google_configuration")
        if not isinstance(self.registration_emails, frozenset) or len(self.registration_emails) > 1000:
            raise GoogleHandoffError("invalid_google_configuration")

        validated_emails = []
        for email in self.registration_emails:
            if not isinstance(email, str):
                raise GoogleHandoffError("invalid_google_configuration")
            try:
                validated = str(_EMAIL.validate_python(email)).lower()
                validated_emails.append(validated)
            except (ValidationError, TypeError):
                raise GoogleHandoffError("invalid_google_configuration") from None

        object.__setattr__(self, 'registration_emails', frozenset(validated_emails))


@dataclass(frozen=True, slots=True)
class VerifiedGoogleHandoff:
    """Verified Google proof + context; sensitive fields excluded from repr."""
    proof: ProviderProof = field(repr=False)
    intent: str
    return_path: str = field(repr=False)
    actor: LinkActor | None = field(repr=False, default=None)


async def complete_google_handoff(
    transactions: OAuthTransactions,
    config: GoogleHandoffConfig,
    *,
    state: str,
    browser_cookie: str,
    intent: str,
    code: str | None = None,
    provider_error: str | None = None,
    actor: LinkActor | None = None,
    client: httpx.AsyncClient,
) -> VerifiedGoogleHandoff:
    """Complete Google OAuth flow: verify transaction, exchange code, verify proof.

    **Always consumes the transaction first**, even on cancellation or error.
    No retry revives consumed state. Returns only verified proof and context;
    never exposes tokens to caller.

    Args:
        transactions: OAuthTransactions instance (tested with mocked store)
        config: GoogleHandoffConfig with client/secret and registration admission
        state: OAuth state from callback query
        browser_cookie: Binding cookie value from request
        intent: "signin", "register", or "link"
        code: Authorization code from provider (None on cancellation)
        provider_error: Provider error parameter (e.g., "access_denied")
        actor: LinkActor or None (required for intent="link")
        client: httpx.AsyncClient with custom timeout/behavior configured

    Returns:
        VerifiedGoogleHandoff with proof, intent, return_path and actor

    Raises:
        GoogleHandoffError: redacted error code (never sensitive details)
    """

    try:
        consumed = await transactions.consume(
            config.client, intent=intent, state=state,
            browser_cookie=browser_cookie, actor=actor,
        )
    except OAuthTransactionError:
        raise GoogleHandoffError("invalid_oauth_transaction") from None

    if provider_error is not None:
        if provider_error == "access_denied":
            raise GoogleHandoffError("user_cancelled")
        raise GoogleHandoffError("provider_error")

    if not isinstance(code, str) or not code or len(code) > 4096:
        raise GoogleHandoffError("invalid_authorization_code")
    if code != code.strip() or not code.isascii() or not all(c.isprintable() for c in code):
        raise GoogleHandoffError("invalid_authorization_code")

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": config.client.client_id,
        "client_secret": config.client_secret,
        "redirect_uri": config.client.callback_uri,
        "code_verifier": consumed.code_verifier,
    }

    try:
        # One total budget, in addition to each provider request's own deadline.
        async with asyncio.timeout(HANDOFF_TIMEOUT_SECONDS):
            body = await _json_response(client, "POST", GOOGLE_TOKEN_URL, data=token_data)
            id_token = body.get("id_token")
            if (
                not isinstance(id_token, str) or not id_token
                or len(id_token) > MAX_TOKEN_BYTES or not id_token.isascii()
            ):
                raise GoogleHandoffError("invalid_provider_token")
            proof = await verify_google_id_token(
                id_token, client_id=config.client.client_id,
                nonce=consumed.nonce, client=client,
            )
    except ProviderProofError as error:
        code_name = "provider_unavailable" if str(error) == "provider_unavailable" else "invalid_provider_token"
        raise GoogleHandoffError(code_name) from None
    except TimeoutError:
        raise GoogleHandoffError("provider_unavailable") from None

    if consumed.intent == "register":
        if not config.registration_enabled:
            raise GoogleHandoffError("registration_not_allowed")

        verified_email_normalized = (
            proof.verified_email.lower() if proof.verified_email else None
        )
        if not verified_email_normalized or (
            not config.public_registration and verified_email_normalized not in config.registration_emails
        ):
            raise GoogleHandoffError("email_not_allowed")

    return VerifiedGoogleHandoff(
        proof=proof,
        # Public registration explicitly means create-or-sign-in by Google
        # subject. Signin-only transactions still never create accounts.
        intent='continue' if consumed.intent == 'register' and config.public_registration else consumed.intent,
        return_path=consumed.return_path,
        actor=consumed.actor,
    )

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
