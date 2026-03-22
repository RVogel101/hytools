"""Dialect converters: reform/classical and Eastern/Western Armenian conversions."""

from __future__ import annotations

# These are simplified rules for demonstration; real production rules should be formalized.
WA_EA_REVERSE_PAIRS = {
    "բ": "պ",
    "պ": "բ",
    "գ": "կ",
    "կ": "գ",
    "դ": "տ",
    "տ": "դ",
    "ձ": "ծ",
    "ծ": "ձ",
    "ջ": "ճ",
    "ճ": "ջ",
    "վ": "ւ",
    "ւ": "վ",
}

REFORM_CLASSICAL_MAP = {
    "ու": "օ",
    "եալ": "ել",
    "ոյ": "ու",
    "ութիւն": "ություն",
    "ոչ": "ոչ",  # no-op helper
}

def to_western(text: str) -> str:
    return "".join(WA_EA_REVERSE_PAIRS.get(ch, ch) for ch in text)


def to_eastern(text: str) -> str:
    # Use same mapping in reverse as is symmetric for given pairs.
    return "".join(WA_EA_REVERSE_PAIRS.get(ch, ch) for ch in text)


def to_classical(text: str) -> str:
    result = text
    for old, new in REFORM_CLASSICAL_MAP.items():
        result = result.replace(old, new)
    return result


def to_reform(text: str) -> str:
    result = text
    for old, new in REFORM_CLASSICAL_MAP.items():
        result = result.replace(new, old)
    return result
