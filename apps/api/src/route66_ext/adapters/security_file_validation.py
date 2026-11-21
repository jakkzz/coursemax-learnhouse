"""Reviewed native adapter: src.security.file_validation. Preserve native policy and transaction ownership."""
from ._exports import export_native

__all__ = ['validate_upload']
globals().update(export_native('src.security.file_validation', __all__))
