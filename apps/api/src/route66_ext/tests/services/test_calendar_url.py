"""Calendar PDF link fetch through the native SSRF guard; synthetic hosts, no network."""
import asyncio
import socket
import unittest
from unittest.mock import patch
import httpx
from src.route66_ext.services import calendar_url as fetcher

PDF = b'%PDF-1.4 synthetic calendar'
HOSTS = {'files.example': '93.184.216.34', 'cdn.example': '93.184.216.35', 'intranet.example': '10.0.0.5'}


class Peer:
    def __init__(self, ip):
        self.ip = ip

    def get_extra_info(self, name):
        return (self.ip, 443) if name == 'server_addr' else None


def resolve(host, *args, **kwargs):
    if host not in HOSTS:
        raise socket.gaierror('unknown')
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (HOSTS[host], 0))]


class CalendarUrlTests(unittest.TestCase):
    def fetch(self, routes, url='https://files.example/cal/%E0%B8%9B%E0%B8%8F%E0%B8%B4%E0%B8%97%E0%B8%B4%E0%B8%99%201-69.pdf',
              limit=1000, peers=None):
        self.seen = []

        def handler(request):
            self.seen.append(request)
            status, headers, body = routes[str(request.url)]
            peer = (peers or {}).get(request.url.host, HOSTS.get(request.url.host))
            return httpx.Response(status, headers=headers, content=body, extensions={'network_stream': Peer(peer)})

        with patch('src.services.utils.ssrf_guard.socket.getaddrinfo', resolve), \
                patch.object(fetcher, '_transport', httpx.MockTransport(handler)):
            return asyncio.run(fetcher.fetch(url, limit))

    def error(self, *args, **kwargs):
        with self.assertRaises(fetcher.UrlError) as caught:
            self.fetch(*args, **kwargs)
        return caught.exception.status, caught.exception.code

    def test_public_pdf_through_redirect_without_cookies(self):
        start = 'https://files.example/cal/%E0%B8%9B%E0%B8%8F%E0%B8%B4%E0%B8%97%E0%B8%B4%E0%B8%99%201-69.pdf'
        routes = {start: (302, {'location': 'https://cdn.example/x/%E0%B8%9B%E0%B8%8F%E0%B8%B4%E0%B8%97%E0%B8%B4%E0%B8%99%201-69.pdf',
                                'set-cookie': 'session=abc; Path=/; Domain=example'}, b''),
                  'https://cdn.example/x/%E0%B8%9B%E0%B8%8F%E0%B8%B4%E0%B8%97%E0%B8%B4%E0%B8%99%201-69.pdf': (200, {}, PDF)}
        data, name, final = self.fetch(routes)
        self.assertEqual((data, name, final.split('/')[2]), (PDF, 'ปฏิทิน 1-69.pdf', 'cdn.example'))
        self.assertEqual(len(self.seen), 2)
        for request in self.seen:
            self.assertNotIn('cookie', request.headers)
            self.assertNotIn('authorization', request.headers)

    def test_redirect_to_private_or_plain_http_is_refused_before_request(self):
        start = 'https://files.example/a.pdf'
        for target in ('https://intranet.example/a.pdf', 'http://cdn.example/a.pdf', 'https://unknown.example/a.pdf'):
            status = self.error({start: (301, {'location': target}, b'')}, url=start)
            self.assertEqual(status, (422, 'invalid_pdf_url'), target)
            self.assertEqual(len(self.seen), 1)  # the refused hop was never requested

    def test_private_start_and_rebound_peer_are_refused(self):
        self.assertEqual(self.error({}, url='https://intranet.example/a.pdf'), (422, 'invalid_pdf_url'))
        self.assertEqual(self.seen, [])
        routes = {'https://files.example/a.pdf': (200, {}, PDF)}
        for peer in ('10.0.0.5', '93.184.216.99'):
            self.assertEqual(self.error(routes, url='https://files.example/a.pdf', peers={'files.example': peer}),
                             (422, 'invalid_pdf_url'), peer)

    def test_invalid_links(self):
        for url in ('http://files.example/a.pdf', 'https://user:pw@files.example/a.pdf', 'https:///a.pdf',
                    'ftp://files.example/a.pdf', 'https://files.example/a b.pdf', 'https://files.example/' + 'a' * 2048,
                    'https://[', 'https://[::1', 'https://files.example:99999/a.pdf', 'https://files.example:port/a.pdf'):
            self.assertEqual(self.error({}, url=url), (422, 'invalid_pdf_url'), url[:40])
            self.assertEqual(self.seen, [])

    def test_size_limit_declared_and_streamed(self):
        url = 'https://files.example/a.pdf'
        self.assertEqual(self.error({url: (200, {'content-length': '5000'}, PDF)}, url=url), (413, 'too_large'))
        self.assertEqual(self.error({url: (200, {}, PDF + b'x' * 2000)}, url=url), (413, 'too_large'))

    def test_not_pdf_unavailable_and_redirect_loop(self):
        url = 'https://files.example/a.pdf'
        self.assertEqual(self.error({url: (200, {'content-type': 'text/html'}, b'<html>login</html>')}, url=url), (422, 'url_not_pdf'))
        self.assertEqual(self.error({url: (404, {}, b'')}, url=url), (422, 'url_unavailable'))
        self.assertEqual(self.error({url: (302, {}, b'')}, url=url), (422, 'url_unavailable'))
        self.assertEqual(self.error({url: (302, {'location': url}, b'')}, url=url), (422, 'url_unavailable'))
        self.assertEqual(len(self.seen), fetcher.MAX_REDIRECTS + 1)

    def test_network_failure_and_deadline(self):
        url = 'https://files.example/a.pdf'

        def failing(request):
            raise httpx.ConnectTimeout('slow', request=request)

        with patch('src.services.utils.ssrf_guard.socket.getaddrinfo', resolve), \
                patch.object(fetcher, '_transport', httpx.MockTransport(failing)):
            with self.assertRaises(fetcher.UrlError) as caught:
                asyncio.run(fetcher.fetch(url, 1000))
        self.assertEqual(caught.exception.code, 'url_unavailable')

        async def slow(request):
            await asyncio.sleep(5)

        with patch('src.services.utils.ssrf_guard.socket.getaddrinfo', resolve), \
                patch.object(fetcher, '_transport', httpx.MockTransport(slow)), patch.object(fetcher, 'DEADLINE', 0.05):
            with self.assertRaises(fetcher.UrlError) as caught:
                asyncio.run(fetcher.fetch(url, 1000))
        self.assertIn('timed out', caught.exception.message)


if __name__ == '__main__':
    unittest.main()
