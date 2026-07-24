"""Per-document-type handler registry — one document type, one logic.

Each handler module exposes:
    DOC_TYPE: str
    extract(path, filename) -> list[(text, source_ref)]

`get_handler(ext)` routes by file extension. To support a new format, drop a
module in this package and add one line to REGISTRY.
"""
from __future__ import annotations

from types import ModuleType

from . import docx, html, markdown, pdf, pptx, tabular

# extension -> handler module
REGISTRY: dict[str, ModuleType] = {
    ".pdf": pdf,
    ".pptx": pptx,
    ".ppt": pptx,
    ".docx": docx,
    ".doc": docx,
    ".md": markdown,
    ".markdown": markdown,
    ".txt": markdown,
    ".html": html,
    ".htm": html,
    ".xlsx": tabular,
    ".xls": tabular,
    ".csv": tabular,
}

SUPPORTED_EXTS = set(REGISTRY.keys())


def get_handler(ext: str) -> ModuleType | None:
    return REGISTRY.get(ext.lower())
