"""Reviewed native adapter: src.db.courses.courses. Preserve native policy and transaction ownership."""
from ._exports import export_native

__all__ = ['Course']
globals().update(export_native('src.db.courses.courses', __all__))
