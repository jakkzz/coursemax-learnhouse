"""Reviewed native adapter: src.core.events.database. Preserve native policy and transaction ownership."""
from ._exports import export_native

__all__ = ['engine', 'get_db_session']
globals().update(export_native('src.core.events.database', __all__))
