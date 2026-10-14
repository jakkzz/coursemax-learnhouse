"""Bounded fixed-origin public registrar search, not a role/identity authority."""
import asyncio
import re
from urllib.parse import parse_qs, urlsplit
import httpx
from bs4 import BeautifulSoup

URL = 'https://reg.nrru.ac.th/registrar/teach_time.asp'
MAX_BYTES = 512 * 1024
class DirectoryUnavailable(ValueError):
    pass

def student_hint(email, hosted_domain):
    """Institutional-account hint only; never enrollment or registrar verification."""
    if hosted_domain != 'nrru.ac.th' or not isinstance(email, str):
        return None
    match = re.fullmatch(r'([0-9]{9,10})@nrru\.ac\.th', email.lower())
    return match[1] if match else None

def teacher_hint(email, hosted_domain):
    if hosted_domain != 'nrru.ac.th' or not isinstance(email, str):
        return None
    # Numeric BE-year student addresses must never invoke staff recognition.
    match = re.fullmatch(r'([a-z]{2,50})\.[a-z]{1,15}@nrru\.ac\.th', email.lower())
    return match[1] if match else None

def parse_candidates(raw):
    soup = BeautifulSoup(raw.decode('cp874', errors='strict'), 'html.parser')
    if 'ตารางสอนอาจารย์' not in soup.get_text():
        raise DirectoryUnavailable('directory_changed')
    found = {}
    for a in soup.find_all('a', href=True):
        url = urlsplit(a['href'])
        if url.scheme or url.netloc or url.path != 'teach_time.asp':
            continue
        q = parse_qs(url.query)
        if q.get('f_cmd') != ['2']:
            continue
        identifier, code = q.get('officerid', [''])[0], q.get('officercode', [''])[0]
        if not re.fullmatch(r'[0-9]{1,20}', identifier) or not re.fullmatch(r'[0-9]{1,20}', code):
            raise DirectoryUnavailable('directory_changed')
        name_th = ' '.join(a.get_text(' ', strip=True).split())
        cell = a.find_parent('td'); other = cell.find_next_sibling('td') if cell else None
        name_en = ' '.join(other.get_text(' ', strip=True).split()) if other else ''
        if not name_th or len(name_th) > 200 or len(name_en) > 200:
            raise DirectoryUnavailable('directory_changed')
        entry = dict(officer_id=identifier, officer_code=code, name_th=name_th, name_en=name_en)
        if identifier in found and found[identifier] != entry:
            raise DirectoryUnavailable('directory_changed')
        found[identifier] = entry
    if len(found) > 100:
        raise DirectoryUnavailable('directory_changed')
    return list(found.values())

async def search_directory(hint, client=None):
    if not isinstance(hint, str) or not re.fullmatch(r'[a-z]{2,50}', hint):
        raise ValueError('invalid_search_hint')
    async def fetch(c):
        request = httpx.Request('POST', URL,
            data={'f_cmd': '1', 'f_officername': hint, 'f_maxrows': '100'},
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            extensions={'timeout': dict.fromkeys(('connect','read','write','pool'), 8.0)})
        try:
            async with asyncio.timeout(10):
                response = await c.send(request, stream=True, auth=None, follow_redirects=False)
                try:
                    if response.status_code != 200:
                        raise DirectoryUnavailable('directory_unavailable')
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(chunks) + len(chunk) > MAX_BYTES:
                            raise DirectoryUnavailable('directory_unavailable')
                        chunks.extend(chunk)
                    return parse_candidates(bytes(chunks))
                finally:
                    await response.aclose()
        except (httpx.HTTPError, TimeoutError, UnicodeError):
            raise DirectoryUnavailable('directory_unavailable') from None
    if client is not None:
        return await fetch(client)
    async with httpx.AsyncClient(trust_env=False) as c:
        return await fetch(c)

# Preserve private helper names through legacy compatibility imports.
__all__ = [name for name in globals() if not name.startswith("__")]
