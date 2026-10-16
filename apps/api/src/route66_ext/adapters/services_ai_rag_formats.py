"""Reviewed native adapter: src.services.ai.rag.formats. Preserve native PDF text extraction."""
from ._exports import export_native

__all__ = ['pdf_pages']
globals().update(export_native('src.services.ai.rag.formats', __all__))
