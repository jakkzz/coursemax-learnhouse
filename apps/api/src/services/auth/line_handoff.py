"""One-use LINE code exchange. No signup, client tokens, or email inference."""
import asyncio
from dataclasses import dataclass, field
import re
import httpx
from src.services.auth.oauth_transactions import OAuthClient, OAuthTransactionError, LinkActor
from src.services.auth.provider_proof import ProviderProof, ProviderProofError, verify_line_oauth_token, _json_response, MAX_TOKEN_BYTES

LINE_TOKEN_URL = 'https://api.line.me/oauth2/v2.1/token'

class LineHandoffError(ValueError):
    """Redacted error code only."""

@dataclass(frozen=True, slots=True)
class LineHandoffConfig:
    client: OAuthClient
    client_secret: str = field(repr=False)

    def __post_init__(self):
        if (not isinstance(self.client, OAuthClient) or self.client.provider != 'line'
            or not re.fullmatch(r'[0-9]{6,20}', self.client.client_id)
            or not re.fullmatch(r'[0-9]{6,20}', self.client.provider_namespace)
            or not isinstance(self.client_secret, str) or not 16 <= len(self.client_secret) <= 255
            or not self.client_secret.isascii() or not self.client_secret.isprintable()
            or self.client_secret != self.client_secret.strip()):
            raise LineHandoffError('invalid_line_configuration')

@dataclass(frozen=True, slots=True)
class VerifiedLineHandoff:
    proof: ProviderProof = field(repr=False)
    intent: str
    return_path: str = field(repr=False)
    actor: LinkActor | None = field(default=None, repr=False)

async def complete_line_handoff(transactions, config, *, state, browser_cookie, intent,
                                client: httpx.AsyncClient, code=None, provider_error=None, actor=None):
    try:
        consumed = await transactions.consume(config.client, intent=intent, state=state,
                                              browser_cookie=browser_cookie, actor=actor)
    except OAuthTransactionError:
        raise LineHandoffError('invalid_oauth_transaction') from None
    if provider_error is not None:
        raise LineHandoffError('user_cancelled' if provider_error == 'access_denied' else 'provider_error')
    if (not isinstance(code, str) or not 0 < len(code) <= 4096 or not code.isascii()
        or not code.isprintable() or code != code.strip()):
        raise LineHandoffError('invalid_authorization_code')
    try:
        async with asyncio.timeout(10):
            body = await _json_response(client, 'POST', LINE_TOKEN_URL, data={
                'grant_type': 'authorization_code', 'code': code,
                'client_id': config.client.client_id, 'client_secret': config.client_secret,
                'redirect_uri': config.client.callback_uri, 'code_verifier': consumed.code_verifier,
            })
            token = body.get('id_token')
            if not isinstance(token, str) or not token or len(token) > MAX_TOKEN_BYTES or not token.isascii():
                raise LineHandoffError('invalid_provider_token')
            proof = await verify_line_oauth_token(token, client_id=config.client.client_id,
                provider_namespace=config.client.provider_namespace, nonce=consumed.nonce, client=client)
    except ProviderProofError as error:
        raise LineHandoffError('provider_unavailable' if str(error) == 'provider_unavailable' else 'invalid_provider_token') from None
    except TimeoutError:
        raise LineHandoffError('provider_unavailable') from None
    return VerifiedLineHandoff(proof, consumed.intent, consumed.return_path, consumed.actor)
