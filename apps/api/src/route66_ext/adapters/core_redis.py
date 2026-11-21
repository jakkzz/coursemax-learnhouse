"""Reviewed native adapter: src.core.redis. Preserve native policy and transaction ownership."""
from ._exports import export_native

__all__ = ['get_redis_client']
globals().update(export_native('src.core.redis', __all__))
