"""Mock-only HTTP rehearsal. Even a successful report grants no authorization."""
import asyncio
import json
import unittest
from unittest.mock import patch

import httpx

from src.route66_ext.adapters.mapping_dry_run_api import MAX_RESPONSE_BYTES, rehearse_mapping
from src.route66_ext.tests.services.test_mapping_dry_run import fixture


HEADERS = {"content-type": "application/json", "cache-control": "private, no-store"}


def reply(data, status=200, headers=None):
    return httpx.Response(status, headers=HEADERS if headers is None else headers, content=data)


class Chunks(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.read_count = 0

    async def __aiter__(self):
        for chunk in self.chunks:
            self.read_count += 1
            yield chunk


class MappingApiDryRunTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.target, self.catalog, self.projection = fixture()

    async def call(self, replies, target=None):
        seen = []

        async def handler(request):
            seen.append(request)
            value = replies[len(seen) - 1]
            return await value(request) if callable(value) else value

        result = await rehearse_mapping(self.target if target is None else target, httpx.MockTransport(handler))
        self.assertIs(result["authorization_granted"], False)
        self.assertEqual(result["writes_performed"], 0)
        self.assertEqual(result["source"], "offline_extension_http_fixture")
        return result, seen

    def valid_replies(self):
        return [reply(json.dumps(self.catalog)), reply(json.dumps(self.projection))]

    async def test_linked_roundtrip(self):
        result, _ = await self.call(self.valid_replies())
        self.assertEqual(result["status"], "linked")
        self.assertEqual(result["class_id"], 4)

    async def test_null_binding_requires_mapping(self):
        self.catalog["courses"][0].update(registry_course_id=None, course_code=None)
        result, _ = await self.call(self.valid_replies())
        self.assertEqual(result["status"], "mapping_required")

    async def test_duplicate_bad_class_is_still_ambiguous(self):
        self.projection["classes"].append(dict(self.projection["classes"][0], id="bad", manageable=False))
        result, seen = await self.call(self.valid_replies())
        self.assertEqual(result["next_step"], "review_ambiguity")
        self.assertEqual(len(seen), 2)  # No write or retry follows ambiguity.

    async def test_all_non_200s_fail_closed_without_retry(self):
        for code in [201, 204, 301, 302, 307, 308, 401, 403, 404, 409, 429, 500, 503]:
            with self.subTest(code=code):
                result, seen = await self.call([reply(b"private body", code,
                    {**HEADERS, "location": "https://never-contact.invalid/"})])
                self.assertEqual(result["status"], "unavailable")
                self.assertEqual(len(seen), 1)

    async def test_invalid_json_and_duplicate_keys_fail_closed(self):
        for body in [b"{", b'\xff', b'{"courses":[],"courses":[]}',
                     b'{"outer":{"key":1,"key":2}}', b'{"value":NaN}', b'{"value":Infinity}']:
            result, seen = await self.call([reply(body)])
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(len(seen), 1)

    async def test_non_object_json_never_means_empty_catalog(self):
        for body in [b"[]", b"null", b'"text"', b"true", b"12"]:
            result, seen = await self.call([reply(body)])
            self.assertEqual(result["status"], "unavailable")
            self.assertEqual(len(seen), 1)

    async def test_content_type_and_private_cache_contract(self):
        for headers in [{}, {"content-type": "text/plain", "cache-control": "private, no-store"},
                        {"content-type": "application/json"},
                        {"content-type": "application/json", "cache-control": "private"},
                        {"content-type": "application/json", "cache-control": "no-store"}]:
            result, _ = await self.call([reply(b"{}", headers=headers)])
            self.assertEqual(result["status"], "unavailable")

    async def test_valid_json_charset_and_case_insensitive_cache_directives(self):
        responses = self.valid_replies()
        responses[0].headers.update({"content-type": "application/json; charset=utf-8",
                                     "cache-control": "PRIVATE, NO-STORE"})
        result, _ = await self.call(responses)
        self.assertEqual(result["status"], "linked")

    async def test_oversized_body_rejected(self):
        result, _ = await self.call([reply(b"x" * (MAX_RESPONSE_BYTES + 1))])
        self.assertEqual(result["status"], "unavailable")

    async def test_actual_stream_is_consumed_in_bounded_chunks(self):
        stream = Chunks([json.dumps(self.catalog).encode()[:20], json.dumps(self.catalog).encode()[20:]])
        responses = [httpx.Response(200, headers=HEADERS, stream=stream), self.valid_replies()[1]]
        result, _ = await self.call(responses)
        self.assertEqual(result["status"], "linked")
        self.assertEqual(stream.read_count, 2)

    async def test_stream_stops_when_limit_is_exceeded(self):
        stream = Chunks([b"x" * (MAX_RESPONSE_BYTES + 1), b"must not read"])
        result, seen = await self.call([httpx.Response(200, headers=HEADERS, stream=stream)])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(stream.read_count, 1)
        self.assertEqual(len(seen), 1)

    async def test_timeout_error_is_redacted(self):
        async def timeout(request):
            raise httpx.ReadTimeout("PRIVATE fixture contents must not leak")
        result, seen = await self.call([timeout])
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertEqual(len(seen), 1)

    async def test_ordinary_fixture_handler_failures_are_redacted(self):
        for error in [RuntimeError("PRIVATE failure"), ValueError("PRIVATE value"), TypeError("PRIVATE type")]:
            async def fail(request):
                raise error
            result, seen = await self.call([fail])
            self.assertEqual(result["status"], "unavailable")
            self.assertNotIn("PRIVATE", json.dumps(result))
            self.assertEqual(len(seen), 1)

    async def test_ordinary_stream_failure_is_redacted(self):
        class BrokenStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b'{"partial":'
                raise RuntimeError("PRIVATE stream")
        result, seen = await self.call([httpx.Response(200, headers=HEADERS, stream=BrokenStream())])
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertEqual(len(seen), 1)

    async def test_mock_handler_is_also_deadline_bounded(self):
        async def slow(request):
            await asyncio.sleep(1)
            return reply(b"{}")
        with patch("src.route66_ext.adapters.mapping_dry_run_api._READ_TIMEOUT_SECONDS", 0.01):
            result, _ = await self.call([slow])
        self.assertEqual(result["status"], "unavailable")

    async def test_real_or_default_transport_rejected_before_network(self):
        async with httpx.AsyncHTTPTransport() as transport:
            for value in [transport, None, object()]:
                with self.assertRaises(TypeError):
                    await rehearse_mapping(self.target, value)

    async def test_mock_subclass_is_not_an_implicit_production_mode(self):
        class OtherTransport(httpx.MockTransport):
            pass
        with self.assertRaises(TypeError):
            await rehearse_mapping(self.target, OtherTransport(lambda _: reply(b"{}")))

    async def test_urls_and_methods_are_fixed_and_credentials_absent(self):
        self.target.update(base_url="https://never-contact.invalid", token="not accepted", cookie="not accepted")
        _, seen = await self.call(self.valid_replies())
        self.assertEqual([r.method for r in seen], ["GET", "GET"])
        self.assertEqual([str(r.url) for r in seen], [
            "https://learnhouse-fixture.invalid/api/v1/academic-classes/courses",
            "https://learnhouse-fixture.invalid/api/v1/academic-classes"])
        for request in seen:
            self.assertNotIn("authorization", request.headers)
            self.assertNotIn("cookie", request.headers)
            self.assertEqual(request.content, b"")

    async def test_fixture_cookie_cannot_cross_requests(self):
        responses = self.valid_replies()
        responses[0].headers["set-cookie"] = "fixture=private; Path=/; Secure"
        _, seen = await self.call(responses)
        self.assertNotIn("cookie", seen[1].headers)

    async def test_second_failure_never_becomes_empty_roster(self):
        result, seen = await self.call([self.valid_replies()[0], reply(b"private", 503)])
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["class_id"])
        self.assertEqual(len(seen), 2)

    async def test_no_actual_network_or_dns_path(self):
        with patch("httpx.AsyncHTTPTransport.handle_async_request", side_effect=AssertionError("network used")), \
             patch("socket.getaddrinfo", side_effect=AssertionError("DNS used")):
            result, _ = await self.call(self.valid_replies())
        self.assertEqual(result["status"], "linked")

    async def test_cancellation_is_not_swallowed_as_projection_failure(self):
        async def cancel(request):
            raise asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await self.call([cancel])


if __name__ == "__main__":
    unittest.main()
