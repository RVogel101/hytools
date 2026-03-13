"""Normalization and hashing helpers for stable cross-project dedup contracts."""

from __future__ import annotations

import hashlib
import re
import unicodedata

_WS_RE = re.compile(r"\s+")


def normalize_text_for_hash(text: str) -> str:
    """Normalize text using the shared dedup contract.

    Contract: Unicode NFKC + whitespace collapse + trim.
    """

    normalized = unicodedata.normalize("NFKC", text)
    normalized = _WS_RE.sub(" ", normalized).strip()
    return normalized


def sha256_normalized(text: str) -> str:
    """Compute SHA-256 hash from normalized text."""

    normalized = normalize_text_for_hash(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
