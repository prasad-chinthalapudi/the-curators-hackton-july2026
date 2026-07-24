"""Shared helpers used by both ingest phases: identity, manifest, upload listing."""
from __future__ import annotations

import hashlib
import json
import logging
import os

from . import config
from .handlers import SUPPORTED_EXTS

log = logging.getLogger("pih.common")


def doc_id_for(path: str) -> str:
    return os.path.basename(path)


def project_id_for(path: str) -> str:
    """v1: parent folder if foldered, else the filename stem."""
    parent = os.path.basename(os.path.dirname(os.path.abspath(path)))
    if parent and parent != os.path.basename(config.UPLOADS):
        return parent
    return os.path.splitext(os.path.basename(path))[0]


def file_signature(path: str) -> str:
    """Cheap manifest key: hash of abspath + size + mtime."""
    st = os.stat(path)
    return hashlib.sha256(
        f"{os.path.abspath(path)}|{st.st_size}|{int(st.st_mtime)}".encode()
    ).hexdigest()


def load_manifest(path: str = config.MANIFEST) -> dict:
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("manifest unreadable (%s); starting fresh.", e)
    return {}


def save_manifest(manifest: dict, path: str = config.MANIFEST) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def iter_uploads(uploads: str, subset: int | None, full: bool) -> list[str]:
    files = []
    for root, _, names in os.walk(uploads):
        for n in sorted(names):
            if os.path.splitext(n)[1].lower() in SUPPORTED_EXTS:
                files.append(os.path.join(root, n))
    files.sort()
    if not full and subset is not None:
        files = files[:subset]
    return files
