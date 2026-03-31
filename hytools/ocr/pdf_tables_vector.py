"""Priority E: extract tables from vector PDFs using Camelot or Tabula (optional).

Works when tables are drawn with lines/vectors; no raster OCR. Requires optional
dependencies (`camelot-py` and/or `tabula-py`); Ghostscript may be required for
some Camelot backends — see Camelot docs.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _tables_to_text(dfs: list[Any]) -> str:
    """Join DataFrames as simple TSV blocks for plain-text sidecars."""
    parts: list[str] = []
    for i, df in enumerate(dfs, start=1):
        if df is None or getattr(df, "empty", True):
            continue
        try:
            block = df.to_csv(sep="\t", index=False, header=True)
        except Exception as exc:
            logger.debug("DataFrame to_csv failed: %s", exc)
            continue
        block = (block or "").strip()
        if block:
            parts.append(f"[table {i}]\n{block}")
    return "\n\n".join(parts).strip() or ""


def extract_tables_camelot(pdf_path: Path, page_num: int) -> str | None:
    """Read tables on one page with Camelot (lattice then stream). Returns None if unavailable or empty."""
    try:
        import camelot  # type: ignore
    except ImportError:
        return None

    path = Path(pdf_path)
    if not path.is_file() or page_num < 1:
        return None

    pages_arg = str(page_num)
    all_dfs: list[Any] = []

    for flavor in ("lattice", "stream"):
        try:
            tables = camelot.read_pdf(str(path), pages=pages_arg, flavor=flavor)
        except Exception as exc:
            logger.debug("Camelot %s failed for %s p%s: %s", flavor, path.name, page_num, exc)
            continue
        n = getattr(tables, "n", 0) or 0
        for j in range(n):
            try:
                t = tables[j]
                df = getattr(t, "df", None)
                if df is not None and not getattr(df, "empty", True):
                    all_dfs.append(df)
            except Exception as exc:
                logger.debug("Camelot table %d: %s", j, exc)
        if all_dfs:
            break

    if not all_dfs:
        return None
    text = _tables_to_text(all_dfs)
    if text:
        logger.info("Camelot extracted tables from %s page %d", path.name, page_num)
    return text or None


def extract_tables_tabula(pdf_path: Path, page_num: int) -> str | None:
    """Read tables on one page with tabula-py. Returns None if unavailable or empty."""
    try:
        import tabula  # type: ignore
    except ImportError:
        return None

    path = Path(pdf_path)
    if not path.is_file() or page_num < 1:
        return None

    try:
        dfs = tabula.read_pdf(
            str(path),
            pages=page_num,
            multiple_tables=True,
            guess=True,
        )
    except Exception as exc:
        logger.debug("Tabula failed for %s p%s: %s", path.name, page_num, exc)
        return None

    if not dfs:
        return None
    text = _tables_to_text(dfs)
    if text:
        logger.info("Tabula extracted tables from %s page %d", path.name, page_num)
    return text or None


def try_vector_tables(
    pdf_path: Path,
    page_num: int,
    *,
    prefer: str = "camelot",
) -> str | None:
    """Try Camelot, then Tabula (or reverse if prefer='tabula'). Returns combined text or None."""
    path = Path(pdf_path)
    first = extract_tables_camelot if prefer != "tabula" else extract_tables_tabula
    second = extract_tables_tabula if prefer != "tabula" else extract_tables_camelot

    t = first(path, page_num)
    if t:
        return t
    return second(path, page_num)
