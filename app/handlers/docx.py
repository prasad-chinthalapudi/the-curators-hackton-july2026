"""DOCX handler — Word docs are heading-structured, not paged.
source_ref = 'file.docx · heading'."""
from __future__ import annotations

from . import base

DOC_TYPE = "docx"


def extract(path: str, filename: str) -> list[tuple[str, str]]:
    dl_doc = base.convert(path)
    return base.heading_units(base.markdown_of(dl_doc), filename)
