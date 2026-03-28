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

# Exclude Armenian punctuation marks (not words). Included character forms:
#   ։  (U+0589 Armenian full stop)
#   ՝  (U+055D Armenian comma)
#   ՛  (U+055B Armenian apostrophe-like mark)
#   ՞  (U+055E Armenian question mark)
#   « »  (U+00AB U+00BB Armenian ŁQP quotation marks)
#   և  (U+0568 U+0575 Armenian conjunction, treated as stopword here)
#   punctuation-like ASCII runes also excluded by script token regex
# Token regex only matches Armenian letters, excluding the above punctuation.
_ARMENIAN_WORD_RE = re.compile(r"[\u0531-\u0556\u0561-\u0586]+")

# Armenian tokens that are not considered lexical lemma words in this WA definition.
# Includes particles or punctuation-like tokens we exclude from frequencies.
# (Western Armenian-specific rule; 'և' is excluded by project requirement.)
_EXCLUDED_TOKENS = {"և"}


def _tokenize_armenian(text: str) -> list[str]:
    tokens = _ARMENIAN_WORD_RE.findall(text.lower())
    # Skip one-character tokens (punctuation/isolated marks) and explicitly excluded tokens.
    return [t for t in tokens if len(t) > 1 and t not in _EXCLUDED_TOKENS]


def _build_docs_query(config: dict) -> dict:
    """Build MongoDB query for documents to include in frequency aggregation."""
    query = {"text": {"$exists": True, "$ne": ""}}
    scrape_cfg = config.get("ingestion", {}).get("frequency_aggregator", {}) or config.get("scraping", {}).get("frequency_aggregator", {}) or {}
    branch = scrape_cfg.get("internal_language_branch")
    if branch:
        query["metadata.internal_language_branch"] = branch

    # Allow overrides from other stages (e.g. incremental_merge)
    override = scrape_cfg.get("_document_filter")
    if isinstance(override, dict):
        query = {**query, **override}

    return query


def run(config: dict) -> None:
    from hytools.ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for frequency aggregation")

        docs_col = client.documents
        freq_col = client.db["word_frequencies"]
        nayiri_headwords: set[str] = set()

        source_freqs: dict[str, Counter] = {}
        source_doc_counts: dict[str, int] = {}
        source_wa_scores: dict[str, list[float]] = {}
        total_docs = 0

        query = _build_docs_query(config)
        if query.get("metadata.internal_language_branch"):
            logger.info("frequency_aggregator: filtering documents by internal_language_branch=%s", query["metadata.internal_language_branch"])

        cursor = docs_col.find(
            query,
            {"source": 1, "text": 1, "title": 1, "metadata.wa_score": 1},
        )

        for doc in cursor:
            total_docs += 1
            source = doc.get("source", "unknown")
            text = doc.get("text", "")
            words = _tokenize_armenian(text)

            source_doc_counts[source] = source_doc_counts.get(source, 0) + 1
            if source not in source_freqs:
                source_freqs[source] = Counter()
            source_freqs[source].update(words)

            wa_score = float(doc.get("metadata", {}).get("wa_score", 0.0) or 0.0)
            source_wa_scores.setdefault(source, []).append(wa_score)

            if source == "nayiri":
                title = doc.get("title", "").strip()
                if title:
                    nayiri_headwords.add(title)

            if total_docs % 5000 == 0:
                logger.info("Processed %d documents...", total_docs)

        logger.info("Processed %d documents from %d sources", total_docs, len(source_freqs))

        # Resolve weights: target-weighted if config has target_*_pct, else fixed SOURCE_WEIGHTS
        scrape_cfg = config.get("ingestion", {}).get("frequency_aggregator", {}) or config.get("scraping", {}).get("frequency_aggregator", {}) or {}
        incremental = bool(scrape_cfg.get("incremental", False))
        target_pcts = {
            k.replace("target_", "").replace("_pct", ""): v
            for k, v in scrape_cfg.items()
            if k.startswith("target_") and k.endswith("_pct") and isinstance(v, (int, float))
        }
        hybrid_enabled = bool(scrape_cfg.get("hybrid_profile", False))
        source_weight_overrides = scrape_cfg.get("source_weights", {}) if isinstance(scrape_cfg.get("source_weights"), dict) else {}
        wa_score_weight = float(scrape_cfg.get("wa_score_weight", 0.2))

        if target_pcts:
            # Normalize to fractions
            target_pcts = {k: float(v) / 100.0 if v > 1 else float(v) for k, v in target_pcts.items()}
            weight_map = _get_target_weights(source_doc_counts, target_pcts)
            logger.info("Using target-weighted weights for %d sources", len(weight_map))
        else:
            weight_map = {}
            for s in source_freqs:
                base_w = source_weight_overrides.get(s, _source_weight(s))
                if hybrid_enabled:
                    scores = source_wa_scores.get(s, [])
                    avg_wa = sum(scores) / len(scores) if scores else 0.0
                    # WA score is typically around 5.0 threshold; scale around 5
                    wa_factor = 1.0 + wa_score_weight * ((avg_wa - 5.0) / 5.0)
                    wa_factor = max(0.5, min(2.0, wa_factor))
                    weight_map[s] = base_w * wa_factor
                else:
                    weight_map[s] = base_w

        all_words: set[str] = set()
        for freq in source_freqs.values():
            all_words.update(freq.keys())
        logger.info("Unique words across all sources: %d", len(all_words))

        entries: list[dict] = []
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
            })

        entries.sort(key=lambda e: (-e["total_count"], e["word"]))
        for i, entry in enumerate(entries, start=1):
            entry["rank"] = i

        logger.info("Frequency list: %d entries (min_count=%d)", len(entries), MIN_COUNT)

        if incremental:
            # Merge entries into existing word_frequencies collection without drop/rebuild.
            for entry in entries:
                existing = freq_col.find_one({"word": entry["word"]})
                if existing:
                    updates = {"total_count": entry["total_count"]}
                    source_increments = {}
                    source_count_inc = 0
                    for src, cnt in entry["source_counts"].items():
                        if src not in (existing.get("source_counts") or {}):
                            source_count_inc += 1
                        source_increments[f"source_counts.{src}"] = cnt
                    inc_kwargs = {**source_increments, **{"total_count": entry["total_count"]}}
                    if source_count_inc:
                        inc_kwargs["source_count"] = source_count_inc
                    freq_col.update_one({"word": entry["word"]}, {"$inc": inc_kwargs})
                else:
                    freq_col.insert_one(entry)
            freq_col.create_index("word", unique=True)
            freq_col.create_index([("rank", 1)])
            freq_col.create_index([("total_count", -1)])
        else:
            freq_col.drop()
            if entries:
                freq_col.insert_many(entries)
                freq_col.create_index("word", unique=True)
                freq_col.create_index([("rank", 1)])
                freq_col.create_index([("total_count", -1)])

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

        if hybrid_enabled:
            meta_doc["hybrid_profile"] = True
            meta_doc["wa_score_weight"] = wa_score_weight
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
    logging.basicConfig(level=logging.INFO)
    run({})
