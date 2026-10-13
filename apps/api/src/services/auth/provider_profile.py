"""Optional verified-provider attributes. Never used for identity/admission/RBAC."""
from dataclasses import dataclass, field
import re
import unicodedata
from urllib.parse import urlsplit

AVATAR_HOSTS = {
    'google': frozenset({'lh3.googleusercontent.com', 'lh4.googleusercontent.com',
                         'lh5.googleusercontent.com', 'lh6.googleusercontent.com'}),
    'line': frozenset({'profile.line-scdn.net', 'obs.line-scdn.net'}),
}

@dataclass(frozen=True, slots=True)
class ProviderProfile:
    given_name: str | None = field(default=None, repr=False)
    family_name: str | None = field(default=None, repr=False)
    display_name: str | None = field(default=None, repr=False)
    picture: str | None = field(default=None, repr=False)
    locale: str | None = field(default=None, repr=False)


def safe_text(value, maximum=100):
    if not isinstance(value, str):
        return None
    value = unicodedata.normalize('NFC', value.strip())
    if not value or len(value) > maximum or re.search(r'https?://|www\.', value, re.I):
        return None
    if any(unicodedata.category(c) in ('Cc', 'Cs') or c in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069' for c in value):
        return None
    return value


def avatar_url(provider, value):
    if not isinstance(value, str) or not value.isascii() or len(value) > 2048 or any(ord(c) < 33 or ord(c) == 127 for c in value) or '\\' in value:
        return None
    try:
        url = urlsplit(value)
        if (url.scheme != 'https' or url.hostname not in AVATAR_HOSTS.get(provider, ())
            or url.username is not None or url.password is not None or url.port not in (None, 443)
            or url.fragment or not url.path):
            return None
    except ValueError:
        return None
    return value


def extract_profile(provider, claims):
    # Caller must finish provider verification BEFORE invoking this function.
    locale = claims.get('locale')
    locale = locale.replace('_', '-').split('-')[0].lower() if isinstance(locale, str) else None
    return ProviderProfile(
        given_name=safe_text(claims.get('given_name')) if provider == 'google' else None,
        family_name=safe_text(claims.get('family_name')) if provider == 'google' else None,
        display_name=safe_text(claims.get('name'), 160),
        picture=avatar_url(provider, claims.get('picture')),
        locale=locale if provider == 'google' and locale in ('en', 'th') else None,
    )
