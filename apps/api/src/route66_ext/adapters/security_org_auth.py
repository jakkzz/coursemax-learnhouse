"""Reviewed native adapter: src.security.org_auth. Preserve native organization MFA policy."""
from ._exports import export_native

__all__ = ['enforce_org_mfa']
globals().update(export_native('src.security.org_auth', __all__))
