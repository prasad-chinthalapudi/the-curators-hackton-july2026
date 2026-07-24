"""Markdown / plain-text handler — read the file directly (no Docling needed),
split by headings. source_ref = 'file.md · heading' (filename only for .txt)."""
from __future__ import annotations

import logging

from . import base

log = logging.getLogger("pih.handlers")
DOC_TYPE = "markdown"


def extract(path: str, filename: str) -> list[tuple[str, str]]:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        log.error("markdown handler cannot read %s: %s", filename, e)
        return []
    return base.heading_units(text, filename)
