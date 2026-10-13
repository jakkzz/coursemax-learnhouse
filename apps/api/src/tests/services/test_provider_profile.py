"""Offline optional-profile/image tests; no real provider/photo/storage calls."""
import unittest
from io import BytesIO
from unittest.mock import AsyncMock
import httpx
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from src.services.auth.provider_profile import extract_profile, avatar_url
from src.services.users.provider_avatar import download_avatar, normalize_avatar, AvatarImportError, MAX_BYTES


def image_bytes(size=(64,64)):
    out=BytesIO();info=PngInfo();info.add_text('private-fixture','remove-this')
    Image.new('RGB',size,'blue').save(out,format='PNG',pnginfo=info)
    return out.getvalue()

class Stream(httpx.AsyncByteStream):
    def __init__(self,data):self.data=data
    async def __aiter__(self):
        for i in range(0,len(self.data),8192):yield self.data[i:i+8192]

class ProviderProfileTests(unittest.IsolatedAsyncioTestCase):
    def test_google_fields_and_locale_optional(self):
        p=extract_profile('google',{'given_name':' ทดสอบ ','family_name':'Person','name':'Fixture','locale':'th-TH','picture':'https://lh3.googleusercontent.com/a'})
        self.assertEqual(p.given_name,'ทดสอบ');self.assertEqual(p.locale,'th')
        self.assertNotIn('Fixture',repr(p));self.assertNotIn('googleusercontent',repr(p))
    def test_line_display_name_never_split_or_email_imported(self):
        p=extract_profile('line',{'name':'ชื่อเล่น หลายคำ','given_name':'untrusted','family_name':'untrusted','email':'other@example.com','locale':'th'})
        self.assertEqual(p.display_name,'ชื่อเล่น หลายคำ');self.assertIsNone(p.given_name);self.assertIsNone(p.family_name);self.assertIsNone(p.locale)
    def test_malformed_optional_attributes_ignored(self):
        p=extract_profile('google',{'given_name':{},'family_name':'bad\x00','name':'https://phishing.example','picture':{},'locale':{}})
        self.assertIsNone(p.given_name);self.assertIsNone(p.family_name);self.assertIsNone(p.display_name);self.assertIsNone(p.picture)
    def test_bad_urls_rejected(self):
        for u in ['http://lh3.googleusercontent.com/a','https://evil.example/a','https://lh3.googleusercontent.com.evil.example/a','https://u@lh3.googleusercontent.com/a','https://lh3.googleusercontent.com:8443/a','https://lh3.googleusercontent.com/a#x','https://127.0.0.1/a','https://lh3.googleusercontent.com\\@evil.example/a','https://profile.line-scdn.net/a','https://lh3.googleusercontent.com/\ud800','https://lh3.googleusercontent.com/a\x7f']:
            with self.subTest(url=u):self.assertIsNone(avatar_url('google',u))
    def test_decode_resize_metadata_removed(self):
        data=normalize_avatar(image_bytes((800,400)))
        self.assertNotIn(b'remove-this',data)
        with Image.open(BytesIO(data)) as im:self.assertEqual(im.size,(512,256));self.assertEqual(im.format,'PNG')
    def test_jpeg_webp_and_early_webp_canvas_bounds(self):
        for fmt in ('JPEG','WEBP'):
            out=BytesIO();Image.new('RGB',(64,64),'blue').save(out,format=fmt)
            self.assertTrue(normalize_avatar(out.getvalue()).startswith(b'\x89PNG'))
        payload=b'\x00'*4+(4095).to_bytes(3,'little')+(4095).to_bytes(3,'little')
        riff=b'WEBPVP8X'+len(payload).to_bytes(4,'little')+payload
        bad=b'RIFF'+len(riff).to_bytes(4,'little')+riff
        with self.assertRaises(AvatarImportError):normalize_avatar(bad)
        out=BytesIO();Image.new('RGB',(4,4)).save(out,format='WEBP',save_all=True,append_images=[Image.new('RGB',(4,4),'blue')],duration=100)
        with self.assertRaises(AvatarImportError):normalize_avatar(out.getvalue())
    def test_invalid_signature_markup_truncation_and_size(self):
        for data in [b'\x89PNG\r\n\x1a\nnot-an-image',b'<html>bad</html>',b'<svg></svg>',image_bytes()[:24],b'x'*(MAX_BYTES+1),image_bytes((2100,2100))]:
            with self.subTest(size=len(data)),self.assertRaises(AvatarImportError):normalize_avatar(data)
    async def test_download_pins_ip_preserves_host_sni_strips_shared_credentials(self):
        seen=[]
        def handle(req):
            seen.append(req)
            self.assertEqual(req.url.host,'93.184.216.34');self.assertEqual(req.headers['host'],'lh3.googleusercontent.com')
            self.assertEqual(req.extensions['sni_hostname'],'lh3.googleusercontent.com')
            for key in ('authorization','cookie','x-internal-key'):self.assertNotIn(key,req.headers)
            return httpx.Response(200,stream=Stream(image_bytes()))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle),auth=('native','secret'),cookies={'LH_access':'native'},headers={'X-Internal-Key':'native'}) as client:
            data=await download_avatar('google','https://lh3.googleusercontent.com/a',client=client,resolver=AsyncMock(return_value=['93.184.216.34']))
        self.assertTrue(data.startswith(b'\x89PNG'));self.assertEqual(len(seen),1)
    async def test_private_and_mixed_dns_no_request(self):
        handler=unittest.mock.Mock()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            for ips in [[],['127.0.0.1'],['10.0.0.1'],['169.254.169.254'],['::1'],['fc00::1'],['224.0.0.1'],['ff02::1'],['64:ff9b::7f00:1'],['2002:7f00:1::'],['93.184.216.34','192.168.0.1']]:
                with self.assertRaises(AvatarImportError):await download_avatar('google','https://lh3.googleusercontent.com/a',client=client,resolver=AsyncMock(return_value=ips))
        handler.assert_not_called()
    async def test_redirect_compression_and_oversized_responses_rejected(self):
        for status,headers,body in [(302,{'Location':'https://evil.example/a'},b''),(200,{'Content-Encoding':'gzip'},b'bad'),(200,{},b'x'*(MAX_BYTES+1))]:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(status,headers=headers,stream=Stream(body)))) as client:
                with self.assertRaises(AvatarImportError):await download_avatar('google','https://lh3.googleusercontent.com/a',client=client,resolver=AsyncMock(return_value=['93.184.216.34']))
    async def test_native_filesystem_staging_and_cleanup(self):
        from src.services.auth.profile_import import stage_avatar,remove_staged
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        cfg=SimpleNamespace(hosting_config=SimpleNamespace(content_delivery=SimpleNamespace(type='filesystem')))
        with TemporaryDirectory(dir='/tmp') as root, patch('src.services.utils.upload_content._CONTENT_ROOT',root), patch('config.config.get_learnhouse_config',return_value=cfg), patch('src.services.utils.upload_content.get_learnhouse_config',return_value=cfg):
            canonical=normalize_avatar(image_bytes());name=await stage_avatar(canonical,'user_fixture')
            path=Path(root)/'users/user_fixture/avatars'/name
            self.assertEqual(path.read_bytes(),canonical)
            await remove_staged('user_fixture',name);self.assertFalse(path.exists())
    async def test_partial_native_storage_failure_cleans_own_file(self):
        from src.services.auth.profile_import import stage_avatar
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        cfg=SimpleNamespace(hosting_config=SimpleNamespace(content_delivery=SimpleNamespace(type='filesystem')))
        with TemporaryDirectory(dir='/tmp') as root:
            async def fail(**args):
                path=Path(root)/'users'/args['uuid']/args['directory']/args['file_and_format']
                path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'partial')
                raise OSError('fixture storage error')
            with patch('src.services.utils.upload_content._CONTENT_ROOT',root), patch('config.config.get_learnhouse_config',return_value=cfg), patch('src.services.utils.upload_content.upload_content',new=fail):
                with self.assertRaises(OSError):await stage_avatar(normalize_avatar(image_bytes()),'user_fixture')
            self.assertFalse(list(Path(root).rglob('*.png')))
    async def test_timeout_non_sensitive(self):
        async def handle(req):raise httpx.ConnectTimeout('private-url-subject')
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with self.assertRaises(AvatarImportError) as e:await download_avatar('google','https://lh3.googleusercontent.com/a',client=client,resolver=AsyncMock(return_value=['93.184.216.34']))
        self.assertNotIn('private-url-subject',str(e.exception))
