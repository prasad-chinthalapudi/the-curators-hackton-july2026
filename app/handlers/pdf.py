"""PDF handler — page-grouped units, source_ref = 'file.pdf · page N'."""
from __future__ import annotations

from . import base

DOC_TYPE = "pdf"


def extract(path: str, filename: str) -> list[tuple[str, str]]:
    dl_doc = base.convert(path)
    units = base.page_units(dl_doc, filename, "page")
    if units:
        return units
    # scanned/flat PDF with no page provenance -> fall back to heading split
    return base.heading_units(base.markdown_of(dl_doc), filename)
