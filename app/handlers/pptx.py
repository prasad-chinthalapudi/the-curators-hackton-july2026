"""PPTX handler — slide-grouped units, source_ref = 'deck.pptx · slide N'."""
from __future__ import annotations

from . import base

DOC_TYPE = "pptx"


def extract(path: str, filename: str) -> list[tuple[str, str]]:
    dl_doc = base.convert(path)
    units = base.page_units(dl_doc, filename, "slide")
    if units:
        return units
    return base.heading_units(base.markdown_of(dl_doc), filename)
