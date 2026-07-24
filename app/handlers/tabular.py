"""Tabular handler (xlsx / csv) — one unit per table, rendered as markdown.
source_ref = 'file.xlsx · table N'. Distinct from prose handlers: it walks
Docling's table items rather than page/heading structure."""
from __future__ import annotations

import logging

from . import base

log = logging.getLogger("pih.handlers")
DOC_TYPE = "tabular"


def extract(path: str, filename: str) -> list[tuple[str, str]]:
    dl_doc = base.convert(path)
    units: list[tuple[str, str]] = []
    tables = getattr(dl_doc, "tables", None) or []
    for i, tbl in enumerate(tables, start=1):
        md = ""
        try:
            md = tbl.export_to_markdown(dl_doc)      # docling 2.x signature
        except TypeError:
            try:
                md = tbl.export_to_markdown()
            except Exception as e:
                log.warning("table %d export failed for %s: %s", i, filename, e)
        except Exception as e:
            log.warning("table %d export failed for %s: %s", i, filename, e)
        if md and md.strip():
            units.append((md.strip(), f"{filename} · table {i}"))

    if units:
        return units
    # no discrete tables -> fall back to the whole-sheet markdown
    return base.heading_units(base.markdown_of(dl_doc), filename)
