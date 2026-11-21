"""Reviewed native adapter: src.services.auth.session. Preserve native policy and transaction ownership."""
from ._exports import export_native

__all__ = ['issue_session_or_challenge']
globals().update(export_native('src.services.auth.session', __all__))
