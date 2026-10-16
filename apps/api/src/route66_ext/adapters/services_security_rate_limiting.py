"""Reviewed native adapter: src.services.security.rate_limiting. Preserve native policy and transaction ownership."""
from ._exports import export_native

__all__ = ['get_client_ip', 'enforce_ai_rate_limit']
globals().update(export_native('src.services.security.rate_limiting', __all__))
