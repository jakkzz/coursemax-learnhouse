"""Reviewed native adapter: src.db.user_audit_events. Preserve native policy and transaction ownership."""
from ._exports import export_native

__all__ = ['UserAuditEvent']
globals().update(export_native('src.db.user_audit_events', __all__))
