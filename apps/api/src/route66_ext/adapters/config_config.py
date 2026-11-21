"""Native validated deployment configuration; never accept browser-supplied origins."""
from ._exports import export_native

__all__ = ['get_learnhouse_config']
globals().update(export_native('config.config', __all__))
