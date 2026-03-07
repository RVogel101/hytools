"""CulturaX Armenian dataset downloader.

Streams the Armenian (hy) subset of the CulturaX dataset from HuggingFace
and saves documents to the raw data directory.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CHECKPOINT_NAME = ".culturax_checkpoint.json"


def _load_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {"processed": 0, "written": 0}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
            return {
                "processed": int(data.get("processed", 0)),
                "written": int(data.get("written", 0)),
            }
    except Exception:
        return {"processed": 0, "written": 0}


def _save_checkpoint(path: Path, processed: int, written: int) -> None:
    path.write_text(
        json.dumps({"processed": processed, "written": written}, indent=2),
        encoding="utf-8",
    )


def _try_wa_filter(text: str) -> bool | None:
    """Attempt WA classification; return None if unavailable."""
    try:
        from armenian_corpus_core.scraping._wa_filter import is_western_armenian
        return is_western_armenian(text)
    except ImportError:
        return None


def run(config: dict) -> None:
    """Entry-point: download the Armenian CulturaX subset."""
    from datasets import load_dataset  # type: ignore[import]

    raw_dir = Path(config["paths"]["raw_dir"]) / "culturax"
    raw_dir.mkdir(parents=True, exist_ok=True)

    scrape_cfg = config["scraping"]["culturax"]
    dataset_name: str = scrape_cfg["dataset_name"]
    language: str = scrape_cfg["language"]
    streaming: bool = scrape_cfg.get("streaming", True)
    apply_wa_filter: bool = scrape_cfg.get("apply_wa_filter", True)
    min_chars: int = int(scrape_cfg.get("min_chars", 100))
    max_docs: int | None = scrape_cfg.get("max_docs")

    checkpoint_path = raw_dir / _CHECKPOINT_NAME
    checkpoint = _load_checkpoint(checkpoint_path)
    already_processed = checkpoint["processed"]
    already_written = checkpoint["written"]

    wa_filter = None
    if apply_wa_filter:
        try:
            from armenian_corpus_core.scraping._wa_filter import is_western_armenian
            wa_filter = is_western_armenian
        except ImportError:
            logger.warning("WA filter unavailable, continuing without WA filter")

    logger.info(
        "Loading CulturaX dataset '%s' (language=%s, streaming=%s, resume_from=%d)",
        dataset_name,
        language,
        streaming,
        already_processed,
    )
    dataset = load_dataset(dataset_name, language, split="train", streaming=streaming, trust_remote_code=True)

    out_file = raw_dir / f"{language}_culturax.jsonl"
    processed = 0
    written = already_written
    with open(out_file, "a", encoding="utf-8") as fh:
        for doc in dataset:
            processed += 1

            if processed <= already_processed:
                continue

            text = str(doc.get("text", "") if isinstance(doc, dict) else "")
            if len(text) < min_chars:
                if processed % 10_000 == 0:
                    _save_checkpoint(checkpoint_path, processed, written)
                continue

            if wa_filter is not None:
                try:
                    if not wa_filter(text[:5000]):
                        if processed % 10_000 == 0:
                            _save_checkpoint(checkpoint_path, processed, written)
                        continue
                except Exception:
                    continue

            fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
            written += 1
            if written % 10_000 == 0:
                logger.info("  Written %d documents (processed=%d)…", written, processed)
                _save_checkpoint(checkpoint_path, processed, written)

            if max_docs is not None and written >= max_docs:
                logger.info("Reached max_docs=%d; stopping early.", max_docs)
                break

    _save_checkpoint(checkpoint_path, processed, written)

    logger.info(
        "CulturaX ingest complete: written=%d (processed=%d) → %s",
        written,
        processed,
        out_file,
    )
