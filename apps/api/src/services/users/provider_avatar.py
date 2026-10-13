"""Bounded avatar download: exact hosts, pinned public IP, verified host TLS/SNI.
Never forward login credentials; do not follow redirects or log provider URLs.
"""
import asyncio
from io import BytesIO
import ipaddress
import socket
import warnings
from urllib.parse import urlsplit
import httpx
from PIL import Image, ImageOps
from src.services.auth.provider_profile import avatar_url

MAX_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 4_000_000

class AvatarImportError(ValueError):
    pass

def public_address(value):
    try:
        ip=ipaddress.ip_address(value)
    except ValueError:
        return False
    if not ip.is_global or ip.is_reserved or ip.is_multicast or ip.is_unspecified or ip.is_loopback or ip.is_link_local:
        return False
    if isinstance(ip,ipaddress.IPv6Address):
        if ip.is_site_local or ip.ipv4_mapped or ip.sixtofour or ip.teredo:
            return False
    return True


async def public_addresses(host):
    rows = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    addresses = sorted({row[4][0] for row in rows})
    if not addresses or not all(public_address(ip) for ip in addresses):
        raise AvatarImportError('unsafe_address')
    return addresses

async def download_avatar(provider, url, *, client=None, resolver=public_addresses):
    if not avatar_url(provider, url):
        raise AvatarImportError('unsafe_url')
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(trust_env=False)
    try:
        async with asyncio.timeout(5):
            host = urlsplit(url).hostname
            addresses = await resolver(host)
            # Check injected resolver results too; pin the numeric destination.
            if not addresses or not all(public_address(ip) for ip in addresses):
                raise AvatarImportError('unsafe_address')
            target = httpx.URL(url).copy_with(host=addresses[0])
            request = httpx.Request('GET', target, headers={'Host': host, 'Accept': 'image/png,image/jpeg,image/webp', 'Accept-Encoding': 'identity'},
                extensions={'sni_hostname': host, 'timeout': dict.fromkeys(('connect','read','write','pool'), 5)})
            response = await client.send(request, stream=True, auth=None, follow_redirects=False)
            try:
                if response.status_code != 200 or response.headers.get('content-encoding', 'identity').lower() != 'identity':
                    raise AvatarImportError('image_unavailable')
                data = bytearray()
                async for chunk in response.aiter_raw():
                    if len(data) + len(chunk) > MAX_BYTES:
                        raise AvatarImportError('image_too_large')
                    data.extend(chunk)
                return bytes(data)
            finally:
                await response.aclose()
    except (httpx.HTTPError, TimeoutError, OSError, ValueError):
        raise AvatarImportError('image_unavailable') from None
    finally:
        if own_client:
            await client.aclose()


def _bounded_webp_header(data):
    # WebP's animation decoder can allocate its canvas during Image.open,
    # before Pillow exposes dimensions. Validate RIFF canvas/frame sizes first.
    if data[:4] != b'RIFF' or data[8:12] != b'WEBP':
        return
    if int.from_bytes(data[4:8],'little')+8 != len(data):
        raise AvatarImportError('invalid_image')
    dimensions=[];offset=12
    while offset+8 <= len(data):
        tag=data[offset:offset+4];size=int.from_bytes(data[offset+4:offset+8],'little')
        payload=data[offset+8:offset+8+size]
        if len(payload)!=size or tag in (b'ANIM',b'ANMF'):
            raise AvatarImportError('invalid_image')
        if tag==b'VP8X':
            if len(payload)!=10 or payload[0]&2:raise AvatarImportError('invalid_image')
            dimensions.append((1+int.from_bytes(payload[4:7],'little'),1+int.from_bytes(payload[7:10],'little')))
        elif tag==b'VP8L':
            if len(payload)<5 or payload[0]!=0x2f:raise AvatarImportError('invalid_image')
            bits=int.from_bytes(payload[1:5],'little');dimensions.append((1+(bits&0x3fff),1+((bits>>14)&0x3fff)))
        elif tag==b'VP8 ':
            if len(payload)<10 or payload[3:6]!=b'\x9d\x01\x2a':raise AvatarImportError('invalid_image')
            dimensions.append((int.from_bytes(payload[6:8],'little')&0x3fff,int.from_bytes(payload[8:10],'little')&0x3fff))
        offset+=8+size+(size&1)
    if not dimensions or offset!=len(data) or len(set(dimensions))!=1:
        raise AvatarImportError('invalid_image')
    w,h=dimensions[0]
    if w<1 or h<1 or w>4096 or h>4096 or w*h>MAX_PIXELS:
        raise AvatarImportError('invalid_image')


def normalize_avatar(data):
    if not isinstance(data, bytes) or not data or len(data) > MAX_BYTES:
        raise AvatarImportError('invalid_image')
    _bounded_webp_header(data)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format not in ('JPEG','PNG','WEBP') or getattr(image, 'n_frames', 1) != 1:
                    raise AvatarImportError('invalid_image')
                if image.width > 4096 or image.height > 4096 or image.width*image.height > MAX_PIXELS:
                    raise AvatarImportError('invalid_image')
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
                image = ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((512,512))
                clean = Image.frombytes('RGB', image.size, image.tobytes())
                out = BytesIO(); clean.save(out, format='PNG')
                result = out.getvalue()
                if len(result) > MAX_BYTES:
                    raise AvatarImportError('invalid_image')
                return result
    except Exception:
        raise AvatarImportError('invalid_image') from None
