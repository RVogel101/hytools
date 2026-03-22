"""Frequency aggregator — builds word frequency list from MongoDB corpus.

Reads text from all documents in MongoDB, computes per-source word counts,
applies source weights (fixed SOURCE_WEIGHTS or target-weighted), and stores
the unified frequency list in the ``word_frequencies`` collection.

Source weights (fixed):
- Wikipedia (hyw): 1.0x — formal/encyclopedic register
- Newspapers:      1.5x — closer to daily usage
- Internet Archive: 1.2x — historical/literary
- Nayiri:          boolean validation only (in_nayiri flag)

Target-weighted mode (config.scraping.frequency_aggregator.target_*_pct):
- Defines desired source-type distribution (e.g. 25% newspaper, 15% wikipedia).
- Computes current distribution from document counts; derives per-source weight
  as target_pct / current_pct (capped); applies when aggregating so frequencies
  approximate the target mix as more documents are digitized.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SOURCE_WEIGHTS = {
    "wikipedia": 1.0,
    "wikipedia_wa": 1.0,
    "wikipedia_ea": 0.5,
    "wikisource": 1.0,
    "newspaper": 1.5,
    "eastern_armenian_news": 0.5,
    "rss_news": 1.5,
    "archive_org": 1.2,
    "hathitrust": 1.2,
    "loc": 1.2,
    "dpla": 1.0,
    "gallica": 1.2,
    "gomidas": 1.2,
    "culturax": 0.8,
    "english_sources": 0.3,
    "nayiri": 1.0,
    "mss_nkr": 1.2,
}


def _source_weight(source: str) -> float:
    """Resolve weight for source; supports prefix match (e.g. newspaper:aztag -> newspaper)."""
    w = SOURCE_WEIGHTS.get(source)
    if w is not None:
        return w
    prefix = source.split(":")[0] if ":" in source else source
    return SOURCE_WEIGHTS.get(prefix, 1.0)


def _get_target_weights(
    source_doc_counts: dict[str, int],
    target_pcts: dict[str, float],
) -> dict[str, float]:
    """Compute per-source weights so that weighted counts approximate target distribution.

    weight[source] = target_pct[source] / (current_pct[source] or 1e-6), capped to [0.1, 10].
    Sources not in target_pcts get weight 1.0.
    """
    total_docs = sum(source_doc_counts.values())
    if total_docs == 0:
        return {s: 1.0 for s in source_doc_counts}

    weights = {}
    for source, count in source_doc_counts.items():
        current_pct = count / total_docs
        target_pct = target_pcts.get(source) or target_pcts.get(source.split(":")[0])
        if target_pct is None or target_pct <= 0:
            weights[source] = 1.0
            continue
        if current_pct < 1e-6:
            current_pct = 1e-6
        w = target_pct / current_pct
        weights[source] = max(0.1, min(10.0, w))
    return weights

MIN_COUNT = 2

_ARMENIAN_WORD_RE = re.compile(r"[\u0530-\u058F\u0560-\u058F]+")


def _tokenize_armenian(text: str) -> list[str]:
    return _ARMENIAN_WORD_RE.findall(text.lower())


def run(config: dict) -> None:
    from ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for frequency aggregation")

        docs_col = client.documents
        freq_col = client.db["word_frequencies"]
        nayiri_headwords: set[str] = set()

        source_freqs: dict[str, Counter] = {}
        source_doc_counts: dict[str, int] = {}
        total_docs = 0
        # Counter for aggregated Western Armenian (wa) when requested
        wa_counter: Counter = Counter()

        cursor = docs_col.find(
            {"text": {"$exists": True, "$ne": ""}},
            {"source": 1, "text": 1, "title": 1},
        )

        def _is_western_doc(d: dict) -> bool:
            """Detect Western Armenian documents strictly by `internal_language_branch`.

            Only returns True when `internal_language_branch` == 'hye-w'.
            Per user requirement, do NOT use fallbacks. Documents missing this
            field are not considered Western for this aggregation.

            Note: some imports store this flag under nested fields (e.g. `metadata.internal_language_branch`).
            Check common nested locations to be robust.
            """
            if not d:
                return False

            # Direct field
            if d.get("internal_language_branch") == "hye-w":
                return True

            # Common nested locations (project uses `metadata` for this)
            meta = d.get("metadata") or {}
            if isinstance(meta, dict) and meta.get("internal_language_branch") == "hye-w":
                return True

            # Also check a few other likely containers if present
            for key in ("processing", "meta", "headers"):
                node = d.get(key)
                if isinstance(node, dict) and node.get("internal_language_branch") == "hye-w":
                    return True

            return False

        for doc in cursor:
            total_docs += 1
            source = doc.get("source", "unknown")
            text = doc.get("text", "")
            words = _tokenize_armenian(text)

            source_doc_counts[source] = source_doc_counts.get(source, 0) + 1
            if source not in source_freqs:
                source_freqs[source] = Counter()
            source_freqs[source].update(words)

            # Aggregate into WA counter when document qualifies
            # We will use the WA aggregate as the primary ranking source if configured
            if aggregate_western_only := (
                (config.get("ingestion", {}) or {}).get("frequency_aggregator", {})
                .get("aggregate_western_only", True)
            ):
                if _is_western_doc(doc):
                    wa_counter.update(words)

            if source == "nayiri":
                title = doc.get("title", "").strip()
                if title:
                    nayiri_headwords.add(title)

            if total_docs % 5000 == 0:
                logger.info("Processed %d documents...", total_docs)

        logger.info("Processed %d documents from %d sources", total_docs, len(source_freqs))

        # Resolve weights: target-weighted if config has target_*_pct, else fixed SOURCE_WEIGHTS
        scrape_cfg = config.get("ingestion", {}).get("frequency_aggregator", {}) or config.get("scraping", {}).get("frequency_aggregator", {}) or {}
        target_pcts = {
            k.replace("target_", "").replace("_pct", ""): v
            for k, v in scrape_cfg.items()
            if k.startswith("target_") and k.endswith("_pct") and isinstance(v, (int, float))
        }
        if target_pcts:
            # Normalize to fractions
            target_pcts = {k: float(v) / 100.0 if v > 1 else float(v) for k, v in target_pcts.items()}
            weight_map = _get_target_weights(source_doc_counts, target_pcts)
            logger.info("Using target-weighted weights for %d sources", len(weight_map))
        else:
            weight_map = {s: _source_weight(s) for s in source_freqs}

        all_words: set[str] = set()
        for freq in source_freqs.values():
            all_words.update(freq.keys())
        logger.info("Unique words across all sources: %d", len(all_words))

        entries: list[dict] = []

        # If WA aggregate mode is enabled (default True), use wa_counter as primary
        aggregate_cfg = config.get("ingestion", {}).get("frequency_aggregator", {}) or config.get("scraping", {}).get("frequency_aggregator", {}) or {}
        aggregate_western_only = aggregate_cfg.get("aggregate_western_only", True)

        if aggregate_western_only:
            logger.info("Building aggregated Western Armenian frequency list (aggregate_western_only=True)")
            # If no WA docs were found, fail loudly per user request
            if not wa_counter:
                raise RuntimeError("No documents with internal_language_branch == 'hye-w' found; aborting Western Armenian aggregation")
            # Build set of words from WA counter
            for word, count in wa_counter.items():
                if count < MIN_COUNT:
                    continue
                # compute per-source breakdown and weighted total for reference
                per_source: dict[str, int] = {}
                source_weighted_total = 0.0
                for src, freq in source_freqs.items():
                    c = freq.get(word, 0)
                    if c > 0:
                        per_source[src] = c
                        w = weight_map.get(src, _source_weight(src))
                        source_weighted_total += c * w

                entries.append({
                    "word": word,
                    "total_count": round(float(count), 2),
                    "wa_total_count": int(count),
                    "source_weighted_total": round(source_weighted_total, 2),
                    "source_counts": per_source,
                    "source_count": len(per_source),
                    "in_nayiri": word in nayiri_headwords,
                    "used_aggregate": "wa",
                })
        else:
            for word in all_words:
                total = 0.0
                per_source: dict[str, int] = {}
                for src, freq in source_freqs.items():
                    count = freq.get(word, 0)
                    if count > 0:
                        per_source[src] = count
                        weight = weight_map.get(src, _source_weight(src))
                        total += count * weight

                if total < MIN_COUNT:
                    continue

                entries.append({
                    "word": word,
                    "total_count": round(total, 2),
                    "source_counts": per_source,
                    "source_count": len(per_source),
                    "in_nayiri": word in nayiri_headwords,
                    "used_aggregate": "per_source",
                })

        entries.sort(key=lambda e: (-e["total_count"], e["word"]))
        for i, entry in enumerate(entries, start=1):
            entry["rank"] = i

        # Compute difficulty components and composite Option B ranking
        try:
            from linguistics.morphology.difficulty import analyze_word, score_word_difficulty
        except Exception:
            analyze_word = None
            score_word_difficulty = None

        max_rank = max((e["rank"] for e in entries), default=1)
        alpha = aggregate_cfg.get("composite_alpha", 0.85)
        beta = aggregate_cfg.get("composite_beta", 0.15)

        for entry in entries:
            word = entry.get("word")
            # default difficulty via generic scorer if available
            difficulty = None
            phonetic = None
            orthographic = None
            try:
                if analyze_word:
                    analysis = analyze_word(word, pos="other")
                    difficulty = float(getattr(analysis, "overall_difficulty", 0.0))
                    phonetic = float(getattr(analysis, "phonetic_score", 0.0))
                    orthographic = float(getattr(analysis, "orthographic_score", 0.0))
                elif score_word_difficulty:
                    difficulty = float(score_word_difficulty(word, pos="other"))
                else:
                    difficulty = 1.0
            except Exception:
                difficulty = 1.0

            entry["difficulty"] = round(float(difficulty), 3)
            if phonetic is not None:
                entry["phonetic_score"] = round(float(phonetic), 3)
            else:
                entry.setdefault("phonetic_score", 0.0)
            if orthographic is not None:
                entry["orthographic_score"] = round(float(orthographic), 3)
            else:
                entry.setdefault("orthographic_score", 0.0)

            # normalized frequency f in [0,1] (1.0 = most frequent)
            if max_rank <= 1:
                f_norm = 1.0
            else:
                f_norm = 1.0 - (entry["rank"] - 1) / float(max_rank - 1)

            # normalized difficulty d_norm in [0,1] where higher = easier
            d_norm = 1.0 - min(max(entry["difficulty"] / 10.0, 0.0), 1.0)

            composite = float(alpha) * f_norm + float(beta) * d_norm
            entry["composite_score"] = round(float(composite), 6)

        # Reorder by composite score (Option B) and reassign ranks
        entries.sort(key=lambda e: (-e.get("composite_score", 0.0), -e["total_count"], e["word"]))
        for i, entry in enumerate(entries, start=1):
            entry["rank"] = i

        logger.info("Frequency list: %d entries (min_count=%d)", len(entries), MIN_COUNT)

        freq_col.drop()
        if entries:
            freq_col.insert_many(entries)
            freq_col.create_index("word", unique=True)
            freq_col.create_index([("rank", 1)])
            freq_col.create_index([("total_count", -1)])
            # index composite and difficulty for fast queries
            freq_col.create_index([("composite_score", -1)])
            freq_col.create_index([("difficulty", -1)])

        meta_doc = {
            "stage": "frequency_aggregator",
            "timestamp": datetime.now(timezone.utc),
            "total_docs_processed": total_docs,
            "unique_words": len(all_words),
            "entries_stored": len(entries),
            "sources": list(source_freqs.keys()),
            "nayiri_headwords": len(nayiri_headwords),
        }
        if target_pcts:
            meta_doc["target_weighted"] = True
            meta_doc["target_pcts"] = target_pcts
            meta_doc["source_doc_counts"] = source_doc_counts
            meta_doc["weights_used"] = weight_map
        client.metadata.replace_one(
            {"stage": "frequency_aggregator"},
            meta_doc,
            upsert=True,
        )

        print(f"Frequency list: {len(entries)} words from {total_docs} documents")
        print(f"Sources: {list(source_freqs.keys())}")
        if target_pcts:
            print("Weights: target-weighted")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Run frequency aggregator")
    parser.add_argument("--composite-alpha", type=float, default=None,
                        help="Alpha weight for composite ranking (0..1)."
                        )
    parser.add_argument("--composite-beta", type=float, default=None,
                        help="Beta weight for composite ranking (0..1)."
                        )
    parser.add_argument("--config", type=str, default=None,
                        help="Optional path to YAML config to pass through.")

    args = parser.parse_args()

    cfg = {}
    if args.config:
        try:
            import yaml
            with open(args.config, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
        except Exception as e:
            logging.error("Failed to load config file: %s", e)
            raise

    # Validate composite weights if provided
    if args.composite_alpha is not None or args.composite_beta is not None:
        a = args.composite_alpha if args.composite_alpha is not None else cfg.get('ingestion', {}).get('frequency_aggregator', {}).get('composite_alpha', 0.85)
        b = args.composite_beta if args.composite_beta is not None else cfg.get('ingestion', {}).get('frequency_aggregator', {}).get('composite_beta', 0.15)
        try:
            a = float(a)
            b = float(b)
        except Exception:
            raise SystemExit("composite_alpha and composite_beta must be floats")
        if not (0.0 <= a <= 1.0 and 0.0 <= b <= 1.0):
            raise SystemExit("composite_alpha and composite_beta must be between 0 and 1")
        if abs((a + b) - 1.0) > 1e-6:
            logging.warning("composite_alpha + composite_beta != 1.0; normalizing weights")
            s = a + b
            if s > 0:
                a = a / s
                b = b / s
        # inject into cfg
        cfg.setdefault('ingestion', {}).setdefault('frequency_aggregator', {})['composite_alpha'] = a
        cfg.setdefault('ingestion', {}).setdefault('frequency_aggregator', {})['composite_beta'] = b

    run(cfg)
