"""Fetch a calendar PDF from a public HTTPS link, with the native SSRF guard.

Every hop (including redirects) is resolved and checked, and the connected peer
is verified before any body byte is read. No cookies, credentials or proxy
environment are used; the body is streamed up to the upload size limit.
"""
import asyncio
from pathlib import PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit
import httpx
from src.route66_ext.adapters import services_utils_ssrf_guard as guard

MAX_REDIRECTS = 5
TIMEOUT = httpx.Timeout(15, connect=5)
DEADLINE = 45  # seconds for the whole fetch, all hops included
_transport = None  # tests only: an httpx transport replacing the network


class UrlError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _bad(message='ใส่ลิงก์ https ของไฟล์ PDF ปฏิทินที่เปิดได้สาธารณะ / Enter a public https link to the calendar PDF'):
    return UrlError(422, 'invalid_pdf_url', message)


def _unavailable(detail):
    return UrlError(422, 'url_unavailable', 'เปิดลิงก์นี้ไม่ได้ / This link could not be downloaded (' + detail
                    + '). Check it opens in a browser without signing in, or upload the PDF file.')


def check(url):
    url = (url or '').strip()
    try:
        parts = urlsplit(url)
        parts.port  # raises ValueError for a malformed port
        valid = (len(url) <= 2048 and parts.scheme == 'https' and parts.hostname and parts.username is None
                 and parts.password is None and not any(c.isspace() for c in url))
    except ValueError:
        valid = False
    if not valid:
        raise _bad()
    return url


def filename(url):
    name = PurePosixPath(unquote(urlsplit(url).path)).name.strip()
    name = name if name.lower().endswith('.pdf') else (name + '.pdf' if name else 'calendar.pdf')
    return name[-255:]


async def _hop(client, url, limit):
    try:
        validated = await asyncio.to_thread(guard.resolve_and_validate_url, url, allow_http=False)
    except guard.SSRFBlockedError:
        raise _bad('ลิงก์นี้ไม่ใช่ที่อยู่สาธารณะ / This link does not point to a public web address') from None
    async with client.stream('GET', url) as response:
        try:
            guard.assert_connected_peer_allowed(response, validated)
        except guard.SSRFBlockedError:
            raise _bad('ลิงก์นี้ไม่ใช่ที่อยู่สาธารณะ / This link does not point to a public web address') from None
        if response.is_redirect:
            location = response.headers.get('location')
            if not location:
                raise _unavailable('redirect without a location')
            return None, check(urljoin(url, location))
        if response.status_code != 200:
            raise _unavailable(f'HTTP {response.status_code}')
        declared = response.headers.get('content-length', '')
        if declared.isdigit() and int(declared) > limit:
            raise UrlError(413, 'too_large', 'The linked PDF is larger than 10 MB')
        data = bytearray()
        async for chunk in response.aiter_bytes():
            data += chunk
            if len(data) > limit:
                raise UrlError(413, 'too_large', 'The linked PDF is larger than 10 MB')
        return bytes(data), url


async def fetch(url, limit):
    """Return (pdf bytes, filename, final url) or raise UrlError with a friendly code."""
    url = check(url)
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=TIMEOUT, transport=_transport,
                                 headers={'Accept': 'application/pdf'}) as client:
        try:
            async with asyncio.timeout(DEADLINE):
                for _ in range(MAX_REDIRECTS + 1):
                    client.cookies.clear()  # never carry cookies between hops
                    data, url = await _hop(client, url, limit)
                    if data is not None:
                        break
                else:
                    raise _unavailable('too many redirects')
        except TimeoutError:
            raise _unavailable('timed out') from None
        except httpx.HTTPError as exc:
            raise _unavailable(type(exc).__name__) from None
    if not data.startswith(b'%PDF-'):
        raise UrlError(422, 'url_not_pdf', 'ลิงก์นี้ไม่ใช่ไฟล์ PDF / This link does not download a PDF file. Link directly to the calendar PDF.')
    return data, filename(url), url
