"""Extraction artifacts — the LangChain-free intermediate that Phase 1 pickles
and Phase 2 consumes.

Kept as plain dataclasses (no LangChain / Docling types) so the pickle is stable
across library upgrades and cheap to re-chunk without re-parsing.
"""
from __future__ import annotations

import logging
import os
import pickle
from dataclasses import dataclass, field

log = logging.getLogger("pih.artifacts")

ARTIFACT_VERSION = 1


@dataclass
class ExtractedUnit:
    """One structural unit of a document (a page, slide, heading section, or
    table), with the citation string it will carry into chunks."""
    text: str
    source_ref: str          # e.g. "deck.pptx · slide 4"


@dataclass
class ExtractedDoc:
    path: str
    doc_id: str              # source filename
    project_id: str          # filename stem or parent folder (v1)
    doc_type: str            # 'pdf' | 'pptx' | 'docx' | 'markdown' | 'html' | 'tabular'
    units: list[ExtractedUnit] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)   # extract_metadata() hook output ({} in v1)
    version: int = ARTIFACT_VERSION

    @property
    def n_units(self) -> int:
        return len(self.units)

    @property
    def char_len(self) -> int:
        return sum(len(u.text) for u in self.units)


def pickle_path(extracted_dir: str, doc_id: str) -> str:
    # doc_id is a filename; make it filesystem-safe for the pickle name
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in doc_id)
    return os.path.join(extracted_dir, f"{safe}.pkl")


def save_extracted(ed: ExtractedDoc, extracted_dir: str) -> str:
    os.makedirs(extracted_dir, exist_ok=True)
    path = pickle_path(extracted_dir, ed.doc_id)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(ed, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)  # atomic-ish -> an interrupted run won't leave a half pickle
    return path


def load_extracted(path: str) -> ExtractedDoc:
    with open(path, "rb") as f:
        ed = pickle.load(f)
    if getattr(ed, "version", None) != ARTIFACT_VERSION:
        log.warning("pickle %s has version %s (expected %s) - re-extract if the schema changed.",
                    path, getattr(ed, "version", None), ARTIFACT_VERSION)
    return ed
