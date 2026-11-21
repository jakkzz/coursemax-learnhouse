"""Reviewed native adapter: src.services.orgs.auth_policy. Preserve native policy and transaction ownership."""
from ._exports import export_native

__all__ = ['enforce_login_auth_method']
globals().update(export_native('src.services.orgs.auth_policy', __all__))
