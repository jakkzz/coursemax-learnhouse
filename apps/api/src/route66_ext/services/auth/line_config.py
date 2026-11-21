"""Deny-by-default LINE runtime configuration; no secret/browser projections."""
from dataclasses import dataclass, field
import os
import re
from fastapi import HTTPException
from src.route66_ext.adapters.config_config import get_learnhouse_config
from src.route66_ext.services.auth.line_handoff import LineHandoffConfig, LineHandoffError
from src.route66_ext.services.auth.oauth_transactions import OAuthClient

@dataclass(frozen=True)
class LineSettings:
    handoff: LineHandoffConfig
    org_id: int
    deployment: str
    secret: bytes = field(repr=False)
    liff_id: str | None = None

    @property
    def liff_enabled(self):
        return bool(self.liff_id and os.getenv('LEARNHOUSE_LINE_LIFF_ENABLED','false').lower() == 'true')

def line_settings():
    if os.getenv('LEARNHOUSE_LINE_SUBJECT_LOGIN_ENABLED','false').lower() != 'true':
        raise HTTPException(503,'LINE sign-in is not enabled')
    try:
        hosting=get_learnhouse_config().hosting_config
        if not hosting.ssl:
            raise ValueError()
        channel=os.environ['LINE_LOGIN_CHANNEL_ID']
        provider=os.environ['LEARNHOUSE_LINE_PROVIDER_ID']
        client=OAuthClient('line',channel,'https://'+hosting.domain,provider)
        handoff=LineHandoffConfig(client,os.environ['LINE_LOGIN_CHANNEL_SECRET'])
        org_id=int(os.environ['LEARNHOUSE_LINE_ORG_ID'])
        secret=os.environ['LEARNHOUSE_LINE_OAUTH_TRANSACTION_SECRET'].encode()
        deployment=os.environ['LEARNHOUSE_LINE_OAUTH_DEPLOYMENT']
        liff_id=os.getenv('LEARNHOUSE_LINE_LIFF_ID') or None
        if (org_id <= 0 or len(secret)<32 or not re.fullmatch(r'[a-z0-9_-]{1,59}',deployment)
            or (liff_id is not None and not re.fullmatch(re.escape(channel)+r'-[A-Za-z0-9_-]{1,100}',liff_id))):
            raise ValueError()
        return LineSettings(handoff,org_id,deployment,secret,liff_id)
    except (KeyError,TypeError,ValueError,LineHandoffError):
        raise HTTPException(503,'LINE configuration needs review') from None

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
