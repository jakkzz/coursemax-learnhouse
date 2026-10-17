"""Mock-only HTTP rehearsal of EXISTING EXTENSION projections, not upstream APIs.

No production mode, credentials, configurable origin, write endpoint, native import
or startup registration. A report is advisory and never grants authorization.
"""
from __future__ import annotations

import asyncio
import json

import httpx

from src.route66_ext.services.mapping_dry_run import plan_mapping


_FIXTURE_ORIGIN = "https://learnhouse-fixture.invalid"
_SOURCE = "offline_extension_http_fixture"
_READ_TIMEOUT_SECONDS = 2
MAX_RESPONSE_BYTES = 262144


class _InvalidFixture(ValueError):
    """Private validation failure, never returned with response contents."""


def _unique_keys(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _InvalidFixture
        result[key] = value
    return result


def _reject_constant(value: str):
    raise _InvalidFixture


async def _read(path: str, transport: httpx.MockTransport) -> dict:
    # A fresh client per read prevents even fixture Set-Cookie propagation.
    async with httpx.AsyncClient(base_url=_FIXTURE_ORIGIN, transport=transport,
                                 trust_env=False, follow_redirects=False,
                                 timeout=_READ_TIMEOUT_SECONDS) as client:
        async with client.stream("GET", path, headers={"Accept": "application/json"}) as response:
            media = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            cache = {part.strip().lower() for part in response.headers.get("cache-control", "").split(",")}
            if response.status_code != 200 or media != "application/json" or not {"private", "no-store"} <= cache:
                raise _InvalidFixture
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                    raise _InvalidFixture
                body.extend(chunk)
            try:
                data = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_keys,
                                  parse_constant=_reject_constant)
            except (ValueError, UnicodeError, RecursionError):
                raise _InvalidFixture from None
            if not isinstance(data, dict):
                raise _InvalidFixture
            return data


async def rehearse_mapping(target: dict, transport: httpx.MockTransport) -> dict:
    """Read two fixed in-memory HTTP fixtures, then run the non-writing planner.

    MockTransport handlers are trusted test code. This is an offline guard against
    accidental default-network transport, not a sandbox for arbitrary handlers.
    """
    if type(transport) is not httpx.MockTransport:
        raise TypeError("Mapping rehearsal requires an exact httpx.MockTransport")
    try:
        catalog = await asyncio.wait_for(
            _read("/api/v1/academic-classes/courses", transport), _READ_TIMEOUT_SECONDS)
        projection = await asyncio.wait_for(
            _read("/api/v1/academic-classes", transport), _READ_TIMEOUT_SECONDS)
    except Exception:
        # Only fixture reads are inside this boundary. Ordinary handler/stream
        # failures are redacted too; BaseException cancellation still propagates.
        # Invalid transport configuration above and planner bugs below are not hidden.
        return {"status": "unavailable", "next_step": "retry_projection", "class_id": None,
                "course_id": None, "writes_performed": 0, "authorization_granted": False,
                "source": _SOURCE}
    return {**plan_mapping(target, catalog, projection), "source": _SOURCE}
