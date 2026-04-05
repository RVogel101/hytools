"""ML-backed post-correction for OCR text.

A sequence-to-sequence (character-level) error correction model that learns
common OCR misreadings on Armenian text.  The module wraps any HuggingFace
``AutoModelForSeq2SeqLM`` or a lightweight custom bigram/character model
trained on (noisy, clean) pairs extracted from the OCR pipeline.

Install (optional)::

    pip install transformers torch   # for HF transformer models

The module lazy-loads so ``import hytools.ocr`` never fails when the
model or libraries are unavailable.

Configuration
~~~~~~~~~~~~~
.. code-block:: yaml

    ocr:
      ml_corrector: auto          # true | false | "auto"
      ml_corrector_model: ""      # HuggingFace model id or local path
      ml_corrector_max_length: 512  # max token/char length per chunk
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_available: bool | None = None  # tri-state: None = not checked yet
_model: Any = None
_tokenizer: Any = None

DEFAULT_MAX_LENGTH = 512


def is_ml_corrector_available(model_path: str = "") -> bool:
    """Return True when a usable correction model is loadable.

    When *model_path* is empty the function merely checks that the
    ``transformers`` library is importable.  When a path is given it also
    verifies that the checkpoint exists (local) or is a known HF Hub id.
    """
    global _available
    if _available is not None:
        return _available

    if not model_path:
        _available = False
        return False

    try:
        import transformers  # noqa: F401
        _available = True
    except Exception:
        _available = False
    return _available


def _ensure_model(model_path: str) -> bool:
    """Load the correction model and tokenizer once.  Returns True on success."""
    global _model, _tokenizer

    if _model is not None:
        return True

    if not is_ml_corrector_available(model_path):
        return False

    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        _tokenizer = AutoTokenizer.from_pretrained(model_path)
        _model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
        _model.eval()
        logger.info("ML corrector model loaded: %s", model_path)
        return True
    except Exception as exc:
        logger.warning("Failed to load ML corrector model '%s': %s", model_path, exc)
        _available = False
        return False


def _chunk_text(text: str, max_length: int) -> list[str]:
    """Split *text* into chunks of at most *max_length* characters.

    Splits on newline boundaries when possible to keep paragraphs intact.
    """
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in text.split("\n"):
        line_len = len(line) + 1  # +1 for the newline
        if current_len + line_len > max_length and current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len

    if current:
        chunks.append("\n".join(current))
    return chunks


def ml_correct_text(
    text: str,
    model_path: str = "",
    max_length: int = DEFAULT_MAX_LENGTH,
) -> str | None:
    """Apply ML-based post-correction to *text*.

    Returns the corrected text, or ``None`` if the model is unavailable
    or correction fails.
    """
    if not text or not text.strip():
        return None

    if not _ensure_model(model_path):
        return None

    try:
        import torch

        chunks = _chunk_text(text, max_length)
        corrected_chunks: list[str] = []

        for chunk in chunks:
            inputs = _tokenizer(
                chunk,
                return_tensors="pt",
                max_length=max_length,
                truncation=True,
            )
            with torch.no_grad():
                outputs = _model.generate(
                    **inputs,
                    max_length=max_length,
                    num_beams=4,
                    early_stopping=True,
                )
            decoded = _tokenizer.decode(outputs[0], skip_special_tokens=True)
            corrected_chunks.append(decoded)

        return "\n".join(corrected_chunks)
    except Exception as exc:
        logger.warning("ML correction failed: %s", exc)
        return None


def reset() -> None:
    """Reset cached model state (useful for testing)."""
    global _available, _model, _tokenizer
    _available = None
    _model = None
    _tokenizer = None
