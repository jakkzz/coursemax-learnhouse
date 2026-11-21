"""Reviewed native adapter: src.db.user_organizations. Preserve native policy and transaction ownership."""
from ._exports import export_native

__all__ = ['UserOrganization']
globals().update(export_native('src.db.user_organizations', __all__))
