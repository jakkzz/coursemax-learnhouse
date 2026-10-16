"""Reviewed native adapter: src.services.ai.llm. Preserve native provider/model selection."""
from ._exports import export_native

__all__ = ['generate', 'resolve_model_for_org']
globals().update(export_native('src.services.ai.llm', __all__))
