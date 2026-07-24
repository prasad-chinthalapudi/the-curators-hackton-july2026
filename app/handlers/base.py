"""Shared low-level parse primitives for the per-type handlers.

Handlers own their *logic* (which primitive to use, how to label source_ref);
these are just the reusable building blocks so each handler stays small.
"""
from __future__ import annotations

import logging
import os
import re

log = logging.getLogger("pih.handlers")

_converter = None


def convert(path: str):
    """Docling parse -> DoclingDocument (singleton converter)."""
    global _converter
    if _converter is None:
        from docling.document_converter import DocumentConverter
        _converter = DocumentConverter()
    return _converter.convert(path).document


def page_units(dl_doc, filename: str, unit_word: str) -> list[tuple[str, str]]:
    """Group text items by page/slide number -> [(text, 'file · <unit> N')].
    Returns [] if the document exposes no page provenance."""
    pages: dict[object, list[str]] = {}
    order: list[object] = []
    for item, _level in dl_doc.iterate_items():
        text = getattr(item, "text", None)
        if not text or not text.strip():
            continue
        page = None
        prov = getattr(item, "prov", None)
        if prov:
            try:
                page = prov[0].page_no
            except Exception:
                page = None
        if page not in pages:
            pages[page] = []
            order.append(page)
        pages[page].append(text)

    if not any(p is not None for p in order):
        return []

    units: list[tuple[str, str]] = []
    for page in order:
        body = "\n".join(pages[page]).strip()
        if not body:
            continue
        ref = f"{filename} · {unit_word} {page}" if page is not None else filename
        units.append((body, ref))
    return units


_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$")


def heading_units(md: str, filename: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) sections -> [(body, 'file · heading')].
    Whole-doc single unit if there are no headings."""
    sections, current, buf = [], "", []
    for line in md.splitlines():
        m = _HEADING_RE.match(line)
        if m:
            if buf:
                sections.append((current, "\n".join(buf).strip()))
                buf = []
            current = m.group(1).strip()
        else:
            buf.append(line)
    if buf:
        sections.append((current, "\n".join(buf).strip()))

    out = []
    for heading, body in sections:
        if not body.strip():
            continue
        ref = f"{filename} · {heading}" if heading else filename
        out.append((body, ref))
    if not out and md.strip():
        out = [(md.strip(), filename)]
    return out


def markdown_of(dl_doc) -> str:
    try:
        return dl_doc.export_to_markdown()
    except Exception as e:
        log.warning("export_to_markdown failed: %s", e)
        return ""
