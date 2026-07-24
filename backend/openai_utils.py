"""Shared OpenAI helpers — Person A owns this; B imports, never copies.

Signatures B relies on (posted in the channel):
    embed_texts(texts: list[str]) -> list[list[float]]     # EMBED_DIM-length vectors
    chat_json(system: str, user: str, model: str) -> dict  # parsed JSON, fences stripped

Every call is wrapped in try/except with logging, uses exponential backoff on
transient/rate-limit errors, and resolves model ids with a fallback.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import Any, Callable

from . import config

log = logging.getLogger("pih.openai_utils")

_client = None  # lazy singleton


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI  # imported lazily so config import never needs the SDK

        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


# ---------------------------------------------------------------------------
# Retry with exponential backoff on transient / rate-limit errors.
# ---------------------------------------------------------------------------
def _is_transient(exc: Exception) -> bool:
    try:
        import openai

        transient = (
            openai.RateLimitError,
            openai.APIConnectionError,
            openai.APITimeoutError,
            openai.InternalServerError,
        )
        if isinstance(exc, transient):
            return True
        # 5xx / 429 surfaced as APIStatusError
        status = getattr(exc, "status_code", None)
        if status is not None and (status == 429 or status >= 500):
            return True
    except Exception:
        pass
    return False


def _retry(fn: Callable[[], Any], *, what: str, max_attempts: int = 5, base_delay: float = 1.0) -> Any:
    """Call fn(); retry transient failures with exponential backoff (1,2,4,8s...)."""
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - we classify below
            if attempt >= max_attempts or not _is_transient(e):
                log.error("%s failed on attempt %d/%d: %s", what, attempt, max_attempts, e)
                raise
            delay = base_delay * (2 ** (attempt - 1))
            log.warning("%s transient error (attempt %d/%d): %s -- retrying in %.1fs",
                        what, attempt, max_attempts, e, delay)
            time.sleep(delay)


# ---------------------------------------------------------------------------
# embed_texts: batched, retried. Returns one EMBED_DIM vector per input text.
# ---------------------------------------------------------------------------
def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = config.resolve_model(config.EMBED_MODEL, config.EMBED_MODEL)
    client = _get_client()
    out: list[list[float]] = []
    for start in range(0, len(texts), config.EMBED_BATCH):
        batch = texts[start:start + config.EMBED_BATCH]
        # OpenAI rejects empty strings; substitute a single space so indexing stays aligned.
        safe = [t if (t and t.strip()) else " " for t in batch]

        def _call(_safe=safe, _model=model):
            return client.embeddings.create(model=_model, input=_safe)

        resp = _retry(_call, what=f"embed_texts[{start}:{start+len(batch)}]")
        out.extend([d.embedding for d in resp.data])
        log.info("embedded %d/%d texts", min(start + len(batch), len(texts)), len(texts))
    return out


# ---------------------------------------------------------------------------
# chat_json: chat completion -> parsed JSON dict. Strips ``` fences, retries
# a parse failure once (re-asking the model to emit valid JSON only).
# ---------------------------------------------------------------------------
def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # drop opening fence (``` or ```json) and closing fence
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1:]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


def chat_json(system: str, user: str, model: str) -> dict:
    resolved = config.resolve_model(model, config.GEN_MODEL_FALLBACK)
    client = _get_client()

    def _once(sys_msg: str) -> str:
        def _call():
            return client.chat.completions.create(
                model=resolved,
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )
        resp = _retry(_call, what=f"chat_json({resolved})")
        return resp.choices[0].message.content or ""

    try:
        raw = _once(system)
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError as e:
        log.warning("chat_json: parse failed (%s); retrying once with a stricter instruction.", e)
        strict = system + "\n\nReturn ONLY valid minified JSON. No prose, no markdown fences."
        raw = _once(strict)
        try:
            return json.loads(_strip_fences(raw))
        except json.JSONDecodeError as e2:
            log.error("chat_json: parse failed again (%s). Raw head: %.200s", e2, raw)
            raise
    except Exception as e:  # network/model errors already retried inside _retry
        log.error("chat_json failed: %s", e)
        raise


# ---------------------------------------------------------------------------
# caption_image: GPT-5.x vision describe, for A4 image captioning.
# ---------------------------------------------------------------------------
_CAPTION_PROMPT = (
    "Describe this figure/chart/diagram for retrieval. State what it shows and "
    "any key labels, numbers, or entities."
)


def caption_image(image_path: str, model: str | None = None) -> str:
    """Return a retrieval-oriented caption for an image. Empty string on failure
    (caller decides whether to skip the row) — never crashes the run."""
    resolved = config.resolve_model(model or config.GEN_MODEL_PRIMARY, config.GEN_MODEL_FALLBACK)
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    except OSError as e:
        log.error("caption_image: cannot read %s: %s", image_path, e)
        return ""
    ext = os.path.splitext(image_path)[1].lstrip(".").lower() or "png"
    data_url = f"data:image/{ext};base64,{b64}"
    client = _get_client()

    def _call():
        return client.chat.completions.create(
            model=resolved,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": _CAPTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }],
        )

    try:
        resp = _retry(_call, what=f"caption_image({os.path.basename(image_path)})")
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        log.error("caption_image failed for %s: %s", image_path, e)
        return ""
