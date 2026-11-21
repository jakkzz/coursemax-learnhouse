"""Reviewed native adapter: src.db.roles. Preserve native policy and transaction ownership."""
from ._exports import export_native

__all__ = ['Role', 'RoleTypeEnum']
globals().update(export_native('src.db.roles', __all__))
