"""Frequency aggregator — merges word counts from all scraping sources.

Reads per-source frequency files, applies source weights, and produces
a unified Western Armenian frequency list.

Source weights:
- Wikipedia (hyw): 1.0x — formal/encyclopedic register
- Newspapers:      1.5x — closer to daily usage
- Internet Archive: 1.2x — historical/literary
- Nayiri:          boolean validation only (in_nayiri flag)

Output fields per word:
    word, rank, total_count, wiki_count, news_count, ia_count,
    in_nayiri, sources
"""

from __future__ import annotations

import csv
import json
import logging
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

# Source weights for the aggregated frequency count.
SOURCE_WEIGHTS = {
    "wikipedia": 1.0,
    "newspapers": 1.5,
    "archive_org": 1.2,
}

# Minimum total weighted count to include a word in the final list.
MIN_COUNT = 2


def _load_freq_json(path: Path) -> Counter:
    """Load a ``{word: count}`` JSON file into a Counter."""
    if not path.exists():
        logger.warning("Frequency file not found: %s", path)
        return Counter()
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return Counter(data)


def _load_nayiri_headwords(path: Path) -> set[str]:
    """Load Nayiri headwords from JSONL or JSON."""
    headwords: set[str] = set()
    if not path.exists():
        return headwords
    if path.suffix == ".jsonl":
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                    headwords.add(entry.get("headword", ""))
                except json.JSONDecodeError:
                    continue
    else:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            for entry in data:
                headwords.add(entry.get("headword", ""))
        elif isinstance(data, dict):
            headwords = set(data.keys())
    headwords.discard("")
    return headwords


def build_frequency_list(
    wiki_freq: Counter,
    news_freq: Counter,
    ia_freq: Counter,
    nayiri_headwords: set[str],
    min_count: int = MIN_COUNT,
) -> list[dict]:
    """Build the unified, weighted frequency list.

    Returns a list of dicts sorted by ``total_count`` descending.
    """
    all_words: set[str] = set(wiki_freq) | set(news_freq) | set(ia_freq)
    logger.info("Unique words across sources: %d", len(all_words))

    entries: list[dict] = []
    for word in all_words:
        wc = wiki_freq.get(word, 0)
        nc = news_freq.get(word, 0)
        ic = ia_freq.get(word, 0)

        total = (
            wc * SOURCE_WEIGHTS["wikipedia"]
            + nc * SOURCE_WEIGHTS["newspapers"]
            + ic * SOURCE_WEIGHTS["archive_org"]
        )
        if total < min_count:
            continue

        source_count = sum(1 for c in (wc, nc, ic) if c > 0)
        entries.append(
            {
                "word": word,
                "total_count": round(total, 2),
                "wiki_count": wc,
                "news_count": nc,
                "ia_count": ic,
                "in_nayiri": word in nayiri_headwords,
                "sources": source_count,
            }
        )

    entries.sort(key=lambda e: (-e["total_count"], e["word"]))

    for i, entry in enumerate(entries, start=1):
        entry["rank"] = i

    logger.info("Frequency list: %d entries (min_count=%d)", len(entries), min_count)
    return entries


def save_frequency_list(entries: list[dict], output_dir: Path) -> None:
    """Write the frequency list as both JSON and CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "wa_frequency_list.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=1)
    logger.info("Wrote %s (%d entries, %.2f MB)", json_path, len(entries), json_path.stat().st_size / 1e6)

    csv_path = output_dir / "wa_frequency_list.csv"
    if entries:
        fieldnames = ["rank", "word", "total_count", "wiki_count", "news_count", "ia_count", "in_nayiri", "sources"]
        with open(csv_path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(entries)
    logger.info("Wrote %s (%.2f MB)", csv_path, csv_path.stat().st_size / 1e6)


def compute_source_frequencies(
    data_dir: Path,
    word_frequencies_fn=None,
) -> tuple[Counter, Counter, Counter]:
    """Compute per-source word frequencies from raw text files.

    Scans the standard directory layout under *data_dir*/raw/ for each
    source and returns (wiki_freq, news_freq, ia_freq).

    If *word_frequencies_fn* is not provided, attempts to import
    ``armenian_corpus_core.extraction`` for tokenization.
    """
    if word_frequencies_fn is None:
        try:
            from armenian_corpus_core.cleaning.armenian_tokenizer import word_frequencies  # type: ignore[reportMissingImports]
            word_frequencies_fn = word_frequencies
        except ImportError:
            raise ImportError(
                "armenian_corpus_core.cleaning.armenian_tokenizer not available. "
                "Pass word_frequencies_fn or install the extraction extra."
            )

    raw_dir = data_dir / "raw"

    def _count_dir(path: Path) -> Counter:
        freq: Counter = Counter()
        if not path.exists():
            return freq
        for txt in path.rglob("*.txt"):
            text = txt.read_text(encoding="utf-8")
            freq += word_frequencies_fn(text)
        return freq

    wiki_freq = _count_dir(raw_dir / "wikipedia" / "extracted")
    logger.info("Wikipedia: %d unique words", len(wiki_freq))

    news_freq: Counter = Counter()
    news_dir = raw_dir / "newspapers"
    if news_dir.exists():
        news_freq += _count_dir(news_dir)
        for jsonl in news_dir.rglob("*_articles.jsonl"):
            with open(jsonl, encoding="utf-8") as fh:
                for line in fh:
                    try:
                        entry = json.loads(line)
                        news_freq += word_frequencies_fn(entry.get("text", ""))
                    except json.JSONDecodeError:
                        continue
    logger.info("Newspapers: %d unique words", len(news_freq))

    ia_freq = _count_dir(raw_dir / "archive_org")
    logger.info("Internet Archive: %d unique words", len(ia_freq))

    return wiki_freq, news_freq, ia_freq


def run(config: dict) -> None:
    """Entry-point: build the unified WA frequency list."""
    data_dir = Path(config["paths"]["data_root"])

    freq_dir = data_dir / "frequencies"
    wiki_json = freq_dir / "wiki_frequencies.json"
    news_json = freq_dir / "news_frequencies.json"
    ia_json = freq_dir / "ia_frequencies.json"

    if wiki_json.exists() or news_json.exists() or ia_json.exists():
        wiki_freq = _load_freq_json(wiki_json)
        news_freq = _load_freq_json(news_json)
        ia_freq = _load_freq_json(ia_json)
    else:
        wiki_freq, news_freq, ia_freq = compute_source_frequencies(data_dir)

        freq_dir.mkdir(parents=True, exist_ok=True)
        for name, freq in [("wiki", wiki_freq), ("news", news_freq), ("ia", ia_freq)]:
            path = freq_dir / f"{name}_frequencies.json"
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(dict(freq), fh, ensure_ascii=False)
            logger.info("Saved %s (%d words)", path, len(freq))

    nayiri_path = data_dir / "raw" / "nayiri" / "dictionary.jsonl"
    nayiri_headwords = _load_nayiri_headwords(nayiri_path)
    logger.info("Nayiri headwords: %d", len(nayiri_headwords))

    entries = build_frequency_list(wiki_freq, news_freq, ia_freq, nayiri_headwords)
    save_frequency_list(entries, data_dir)
