"""HTML handler — Docling parse, section/heading units.
source_ref = 'file.html · heading'."""
from __future__ import annotations

from . import base

DOC_TYPE = "html"


def extract(path: str, filename: str) -> list[tuple[str, str]]:
    dl_doc = base.convert(path)
    return base.heading_units(base.markdown_of(dl_doc), filename)
