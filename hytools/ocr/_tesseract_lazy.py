"""Lazy import for pytesseract.

Some environments have a broken ``pyarrow`` install that breaks ``pandas`` import;
older ``pytesseract`` versions import ``pandas`` at module load time. Deferring
``import pytesseract`` until OCR runs avoids failing on ``import hytools``.
"""

from __future__ import annotations

from typing import Any

_pt: Any = None


def get_pytesseract() -> Any:
    global _pt
    if _pt is None:
        import pytesseract

        _pt = pytesseract
    return _pt
