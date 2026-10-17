"""Reviewed native adapter: src.services.utils.ssrf_guard. Preserve native public-address checks."""
from ._exports import export_native

__all__ = ['SSRFBlockedError', 'resolve_and_validate_url', 'assert_connected_peer_allowed']
globals().update(export_native('src.services.utils.ssrf_guard', __all__))
