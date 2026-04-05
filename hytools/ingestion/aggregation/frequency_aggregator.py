"""Frequency aggregator — builds word frequency list from MongoDB corpus.

Reads text from corpus documents, stores per-document token state, maintains
raw per-source word totals, applies source weights, and materializes the final
``word_frequencies`` collection.

This module supports two modes:

- Full rebuild: recompute all state from matching corpus documents.
- Incremental update: diff changed documents against stored per-document state,
    update raw source totals, then rematerialize ``word_frequencies``.

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

import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

logger = logging.getLogger(__name__)

WORD_FREQUENCIES_COLLECTION = "word_frequencies"
DOCUMENT_STATE_COLLECTION = "word_frequency_document_state"
SOURCE_TOTALS_COLLECTION = "word_frequency_source_totals"
SOURCE_STATS_COLLECTION = "word_frequency_source_stats"

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


def _get_frequency_config(config: dict) -> dict:
    return (
        config.get("ingestion", {}).get("frequency_aggregator")
        or config.get("scraping", {}).get("frequency_aggregator")
        or {}
    )


def _build_docs_query(config: dict) -> dict:
    """Build MongoDB query for documents to include in frequency aggregation."""
    query = {"text": {"$exists": True, "$ne": ""}}
    scrape_cfg = _get_frequency_config(config)
    branch = scrape_cfg.get("internal_language_branch")
    if branch:
        query["metadata.internal_language_branch"] = branch

    # Allow overrides from other stages (e.g. incremental_merge)
    override = scrape_cfg.get("_document_filter")
    if isinstance(override, dict):
        query = {**query, **override}

    return query


def _query_signature(query: dict) -> str:
    return json.dumps(query, ensure_ascii=False, sort_keys=True, default=str)


def _document_projection() -> dict:
    return {
        "_id": 1,
        "source": 1,
        "title": 1,
        "text": 1,
        "metadata.wa_score": 1,
        "metadata.enrichment_date": 1,
    }


def _normalize_enrichment_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    text = str(value).strip()
    return text or None


def _max_enrichment_date(current: str | None, candidate: str | None) -> str | None:
    if not candidate:
        return current
    if current is None or candidate > current:
        return candidate
    return current


def _build_document_state(doc: dict) -> dict[str, Any]:
    metadata = doc.get("metadata") or {}
    source = doc.get("source", "unknown")
    title = (doc.get("title") or "").strip()
    token_counts = Counter(_tokenize_armenian(doc.get("text", "")))
    headword = title if source == "nayiri" and title else None
    return {
        "_id": doc["_id"],
        "source": source,
        "wa_score": float(metadata.get("wa_score", 0.0) or 0.0),
        "enrichment_date": _normalize_enrichment_date(metadata.get("enrichment_date")),
        "token_counts": dict(token_counts),
        "headword": headword,
        "updated_at": datetime.now(timezone.utc),
    }


def _get_collections(client):
    return (
        client.db[WORD_FREQUENCIES_COLLECTION],
        client.db[DOCUMENT_STATE_COLLECTION],
        client.db[SOURCE_TOTALS_COLLECTION],
        client.db[SOURCE_STATS_COLLECTION],
    )


def _ensure_indexes(freq_col, doc_state_col, source_totals_col, source_stats_col) -> None:
    freq_col.create_index("word", unique=True)
    freq_col.create_index([("rank", 1)])
    freq_col.create_index([("total_count", -1)])

    doc_state_col.create_index([("source", 1)])
    doc_state_col.create_index([("enrichment_date", 1)])

    source_totals_col.create_index("word", unique=True)
    source_totals_col.create_index([("source_count", -1)])

    source_stats_col.create_index([("source", 1)], unique=True)


def _load_source_stats(source_stats_col) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for doc in source_stats_col.find({}, {"source": 1, "doc_count": 1, "wa_score_sum": 1, "wa_score_count": 1}):
        source = doc.get("source") or doc.get("_id")
        if not source:
            continue
        stats[str(source)] = {
            "doc_count": float(doc.get("doc_count", 0) or 0),
            "wa_score_sum": float(doc.get("wa_score_sum", 0.0) or 0.0),
            "wa_score_count": float(doc.get("wa_score_count", 0) or 0),
        }
    return stats


def _resolve_weight_info(source_stats: dict[str, dict[str, float]], config: dict) -> dict[str, Any]:
    scrape_cfg = _get_frequency_config(config)
    source_doc_counts = {
        source: int(stats.get("doc_count", 0) or 0)
        for source, stats in source_stats.items()
        if int(stats.get("doc_count", 0) or 0) > 0
    }
    target_pcts = {
        key.replace("target_", "").replace("_pct", ""): value
        for key, value in scrape_cfg.items()
        if key.startswith("target_")
        and key.endswith("_pct")
        and isinstance(value, (int, float))
    }
    hybrid_enabled = bool(scrape_cfg.get("hybrid_profile", False))
    source_weight_overrides = (
        scrape_cfg.get("source_weights", {})
        if isinstance(scrape_cfg.get("source_weights"), dict)
        else {}
    )
    wa_score_weight = float(scrape_cfg.get("wa_score_weight", 0.2))

    if target_pcts:
        normalized_targets = {
            key: float(value) / 100.0 if value > 1 else float(value)
            for key, value in target_pcts.items()
        }
        weight_map = _get_target_weights(source_doc_counts, normalized_targets)
    else:
        normalized_targets = None
        weight_map: dict[str, float] = {}
        for source, stats in source_stats.items():
            base_weight = float(source_weight_overrides.get(source, _source_weight(source)))
            if hybrid_enabled:
                wa_count = float(stats.get("wa_score_count", 0) or 0)
                wa_sum = float(stats.get("wa_score_sum", 0.0) or 0.0)
                avg_wa = (wa_sum / wa_count) if wa_count else 0.0
                wa_factor = 1.0 + wa_score_weight * ((avg_wa - 5.0) / 5.0)
                wa_factor = max(0.5, min(2.0, wa_factor))
                weight_map[source] = base_weight * wa_factor
            else:
                weight_map[source] = base_weight

    return {
        "weight_map": weight_map,
        "source_doc_counts": source_doc_counts,
        "target_pcts": normalized_targets,
        "hybrid_enabled": hybrid_enabled,
        "wa_score_weight": wa_score_weight,
    }


def _build_materialized_entries(
    source_total_docs: Iterable[dict[str, Any]],
    weight_map: dict[str, float],
) -> tuple[list[dict[str, Any]], int]:
    entries: list[dict[str, Any]] = []
    unique_words = 0

    for doc in source_total_docs:
        unique_words += 1
        source_counts = {
            source: int(count)
            for source, count in (doc.get("source_counts") or {}).items()
            if int(count) > 0
        }
        total = 0.0
        for source, count in source_counts.items():
            total += count * weight_map.get(source, _source_weight(source))

        if total < MIN_COUNT:
            continue

        entries.append(
            {
                "word": doc["word"],
                "total_count": round(total, 2),
                "source_counts": source_counts,
                "source_count": len(source_counts),
                "in_nayiri": int(doc.get("nayiri_headword_count", 0) or 0) > 0,
            }
        )

    entries.sort(key=lambda entry: (-entry["total_count"], entry["word"]))
    for rank, entry in enumerate(entries, start=1):
        entry["rank"] = rank
    return entries, unique_words


def _replace_materialized_collection(freq_col, entries: list[dict[str, Any]]) -> None:
    freq_col.drop()
    if entries:
        freq_col.insert_many(entries)
    freq_col.create_index("word", unique=True)
    freq_col.create_index([("rank", 1)])
    freq_col.create_index([("total_count", -1)])


def _update_source_stats(
    source_stats_col,
    source: str,
    *,
    doc_count_delta: int = 0,
    wa_score_delta: float = 0.0,
    wa_score_count_delta: int = 0,
) -> None:
    increments: dict[str, float | int] = {}
    if doc_count_delta:
        increments["doc_count"] = doc_count_delta
    if wa_score_delta:
        increments["wa_score_sum"] = wa_score_delta
    if wa_score_count_delta:
        increments["wa_score_count"] = wa_score_count_delta
    if not increments:
        return

    source_stats_col.update_one(
        {"_id": source},
        {
            "$inc": increments,
            "$setOnInsert": {"_id": source, "source": source},
        },
        upsert=True,
    )


def _update_source_word_counts(source_totals_col, source: str, counts: Counter, sign: int, touched_words: set[str]) -> None:
    for word, count in counts.items():
        delta = int(count) * sign
        if not delta:
            continue
        touched_words.add(word)
        source_totals_col.update_one(
            {"word": word},
            {
                "$inc": {f"source_counts.{source}": delta},
                "$setOnInsert": {
                    "word": word,
                    "source_count": 0,
                    "nayiri_headword_count": 0,
                },
            },
            upsert=True,
        )


def _update_headword_count(source_totals_col, word: str | None, delta: int, touched_words: set[str]) -> None:
    if not word or not delta:
        return
    touched_words.add(word)
    source_totals_col.update_one(
        {"word": word},
        {
            "$inc": {"nayiri_headword_count": delta},
            "$setOnInsert": {
                "word": word,
                "source_count": 0,
                "source_counts": {},
            },
        },
        upsert=True,
    )


def _cleanup_source_stats(source_stats_col, touched_sources: set[str]) -> None:
    for source in touched_sources:
        current = source_stats_col.find_one({"_id": source})
        if current is None:
            continue

        doc_count = max(int(current.get("doc_count", 0) or 0), 0)
        wa_score_count = max(int(current.get("wa_score_count", 0) or 0), 0)
        wa_score_sum = float(current.get("wa_score_sum", 0.0) or 0.0)
        if wa_score_count == 0:
            wa_score_sum = 0.0

        if doc_count == 0 and wa_score_count == 0:
            source_stats_col.delete_one({"_id": source})
            continue

        source_stats_col.update_one(
            {"_id": source},
            {
                "$set": {
                    "source": source,
                    "doc_count": doc_count,
                    "wa_score_count": wa_score_count,
                    "wa_score_sum": wa_score_sum,
                }
            },
        )


def _cleanup_source_totals(source_totals_col, touched_words: set[str]) -> None:
    for word in touched_words:
        current = source_totals_col.find_one({"word": word})
        if current is None:
            continue

        normalized_counts = {
            source: int(count)
            for source, count in (current.get("source_counts") or {}).items()
            if int(count) > 0
        }
        headword_count = max(int(current.get("nayiri_headword_count", 0) or 0), 0)

        if not normalized_counts and headword_count <= 0:
            source_totals_col.delete_one({"word": word})
            continue

        source_totals_col.update_one(
            {"word": word},
            {
                "$set": {
                    "source_counts": normalized_counts,
                    "source_count": len(normalized_counts),
                    "nayiri_headword_count": headword_count,
                }
            },
        )


def _apply_document_delta(
    source_totals_col,
    source_stats_col,
    old_state: dict[str, Any] | None,
    new_state: dict[str, Any],
    touched_words: set[str],
    touched_sources: set[str],
) -> None:
    new_source = str(new_state.get("source", "unknown"))
    new_counts = Counter(new_state.get("token_counts") or {})
    new_wa_score = float(new_state.get("wa_score", 0.0) or 0.0)
    new_headword = new_state.get("headword")
    touched_sources.add(new_source)

    if old_state is None:
        _update_source_stats(
            source_stats_col,
            new_source,
            doc_count_delta=1,
            wa_score_delta=new_wa_score,
            wa_score_count_delta=1,
        )
        _update_source_word_counts(source_totals_col, new_source, new_counts, 1, touched_words)
        _update_headword_count(source_totals_col, new_headword, 1, touched_words)
        return

    old_source = str(old_state.get("source", "unknown"))
    old_counts = Counter(old_state.get("token_counts") or {})
    old_wa_score = float(old_state.get("wa_score", 0.0) or 0.0)
    old_headword = old_state.get("headword")
    touched_sources.add(old_source)

    if old_source != new_source:
        _update_source_stats(
            source_stats_col,
            old_source,
            doc_count_delta=-1,
            wa_score_delta=-old_wa_score,
            wa_score_count_delta=-1,
        )
        _update_source_stats(
            source_stats_col,
            new_source,
            doc_count_delta=1,
            wa_score_delta=new_wa_score,
            wa_score_count_delta=1,
        )
        _update_source_word_counts(source_totals_col, old_source, old_counts, -1, touched_words)
        _update_source_word_counts(source_totals_col, new_source, new_counts, 1, touched_words)
    else:
        wa_delta = new_wa_score - old_wa_score
        if wa_delta:
            _update_source_stats(source_stats_col, new_source, wa_score_delta=wa_delta)

        for word in set(old_counts) | set(new_counts):
            delta = int(new_counts.get(word, 0) or 0) - int(old_counts.get(word, 0) or 0)
            if not delta:
                continue
            touched_words.add(word)
            source_totals_col.update_one(
                {"word": word},
                {
                    "$inc": {f"source_counts.{new_source}": delta},
                    "$setOnInsert": {
                        "word": word,
                        "source_count": 0,
                        "nayiri_headword_count": 0,
                    },
                },
                upsert=True,
            )

    if old_headword != new_headword:
        _update_headword_count(source_totals_col, old_headword, -1, touched_words)
        _update_headword_count(source_totals_col, new_headword, 1, touched_words)


def _remove_document_state(
    source_totals_col,
    source_stats_col,
    old_state: dict[str, Any],
    touched_words: set[str],
    touched_sources: set[str],
) -> None:
    old_source = str(old_state.get("source", "unknown"))
    old_counts = Counter(old_state.get("token_counts") or {})
    old_wa_score = float(old_state.get("wa_score", 0.0) or 0.0)
    old_headword = old_state.get("headword")
    touched_sources.add(old_source)

    _update_source_stats(
        source_stats_col,
        old_source,
        doc_count_delta=-1,
        wa_score_delta=-old_wa_score,
        wa_score_count_delta=-1,
    )
    _update_source_word_counts(source_totals_col, old_source, old_counts, -1, touched_words)
    _update_headword_count(source_totals_col, old_headword, -1, touched_words)


def _build_frequency_metadata_doc(stage: str, summary: dict[str, Any], query_signature: str) -> dict[str, Any]:
    metadata_doc = {
        "stage": stage,
        "timestamp": datetime.now(timezone.utc),
        "total_docs_processed": summary.get("total_docs_processed", 0),
        "unique_words": summary.get("unique_words", 0),
        "entries_stored": summary.get("entries_stored", 0),
        "sources": summary.get("sources", []),
        "nayiri_headwords": summary.get("nayiri_headwords", 0),
        "query_signature": query_signature,
    }
    if summary.get("last_enrichment_date"):
        metadata_doc["last_enrichment_date"] = summary["last_enrichment_date"]
    if summary.get("source_doc_counts") is not None:
        metadata_doc["source_doc_counts"] = summary["source_doc_counts"]
    if summary.get("weight_map") is not None:
        metadata_doc["weights_used"] = summary["weight_map"]
    if summary.get("target_pcts"):
        metadata_doc["target_weighted"] = True
        metadata_doc["target_pcts"] = summary["target_pcts"]
    if summary.get("hybrid_enabled"):
        metadata_doc["hybrid_profile"] = True
        metadata_doc["wa_score_weight"] = summary.get("wa_score_weight", 0.0)
    if summary.get("touched_words") is not None:
        metadata_doc["touched_words"] = summary["touched_words"]
    if summary.get("docs_processed") is not None:
        metadata_doc["docs_processed"] = summary["docs_processed"]
    if summary.get("removed_docs_processed") is not None:
        metadata_doc["removed_docs_processed"] = summary["removed_docs_processed"]
    if summary.get("note"):
        metadata_doc["note"] = summary["note"]
    return metadata_doc


def _run_full_rebuild(client, config: dict) -> dict[str, Any]:
    docs_col = client.documents
    freq_col, doc_state_col, source_totals_col, source_stats_col = _get_collections(client)
    _ensure_indexes(freq_col, doc_state_col, source_totals_col, source_stats_col)

    source_freqs: dict[str, Counter] = defaultdict(Counter)
    source_doc_counts: Counter = Counter()
    source_wa_sums: Counter = Counter()
    source_wa_counts: Counter = Counter()
    nayiri_headword_counts: Counter = Counter()
    doc_states: list[dict[str, Any]] = []
    total_docs = 0
    last_enrichment_date: str | None = None

    query = _build_docs_query(config)
    if query.get("metadata.internal_language_branch"):
        logger.info(
            "frequency_aggregator: filtering documents by internal_language_branch=%s",
            query["metadata.internal_language_branch"],
        )

    cursor = docs_col.find(query, _document_projection())
    for doc in cursor:
        total_docs += 1
        state = _build_document_state(doc)
        doc_states.append(state)

        source = str(state["source"])
        source_doc_counts[source] += 1
        source_wa_sums[source] += float(state["wa_score"])
        source_wa_counts[source] += 1
        source_freqs[source].update(state["token_counts"])

        if state.get("headword"):
            nayiri_headword_counts[str(state["headword"])] += 1

        last_enrichment_date = _max_enrichment_date(
            last_enrichment_date,
            state.get("enrichment_date"),
        )

        if total_docs % 5000 == 0:
            logger.info("Processed %d documents...", total_docs)

    logger.info("Processed %d documents from %d sources", total_docs, len(source_doc_counts))

    all_words: set[str] = set(nayiri_headword_counts)
    for source_freq in source_freqs.values():
        all_words.update(source_freq.keys())

    source_total_docs: list[dict[str, Any]] = []
    for word in all_words:
        per_source = {
            source: int(freq.get(word, 0))
            for source, freq in source_freqs.items()
            if int(freq.get(word, 0)) > 0
        }
        source_total_docs.append(
            {
                "word": word,
                "source_counts": per_source,
                "source_count": len(per_source),
                "nayiri_headword_count": int(nayiri_headword_counts.get(word, 0) or 0),
            }
        )

    source_stats_docs = [
        {
            "_id": source,
            "source": source,
            "doc_count": int(source_doc_counts.get(source, 0) or 0),
            "wa_score_sum": float(source_wa_sums.get(source, 0.0) or 0.0),
            "wa_score_count": int(source_wa_counts.get(source, 0) or 0),
        }
        for source in sorted(source_doc_counts)
    ]
    source_stats = {
        doc["source"]: {
            "doc_count": float(doc["doc_count"]),
            "wa_score_sum": float(doc["wa_score_sum"]),
            "wa_score_count": float(doc["wa_score_count"]),
        }
        for doc in source_stats_docs
    }
    weight_info = _resolve_weight_info(source_stats, config)
    entries, unique_words = _build_materialized_entries(
        source_total_docs,
        weight_info["weight_map"],
    )

    doc_state_col.drop()
    if doc_states:
        doc_state_col.insert_many(doc_states)
    doc_state_col.create_index([("source", 1)])
    doc_state_col.create_index([("enrichment_date", 1)])

    source_totals_col.drop()
    if source_total_docs:
        source_totals_col.insert_many(source_total_docs)
    source_totals_col.create_index("word", unique=True)
    source_totals_col.create_index([("source_count", -1)])

    source_stats_col.drop()
    if source_stats_docs:
        source_stats_col.insert_many(source_stats_docs)
    source_stats_col.create_index([("source", 1)], unique=True)

    _replace_materialized_collection(freq_col, entries)

    logger.info("Unique words across all sources: %d", unique_words)
    logger.info("Frequency list: %d entries (min_count=%d)", len(entries), MIN_COUNT)

    return {
        "total_docs_processed": total_docs,
        "docs_processed": total_docs,
        "unique_words": unique_words,
        "entries_stored": len(entries),
        "sources": sorted(source_doc_counts),
        "nayiri_headwords": int(sum(nayiri_headword_counts.values())),
        "last_enrichment_date": last_enrichment_date,
        **weight_info,
    }


def run_incremental_update(
    client,
    config: dict,
    query: dict,
    removed_doc_ids: Iterable[Any] | None = None,
) -> dict[str, Any]:
    docs_col = client.documents
    freq_col, doc_state_col, source_totals_col, source_stats_col = _get_collections(client)
    _ensure_indexes(freq_col, doc_state_col, source_totals_col, source_stats_col)

    changed_docs = list(docs_col.find(query, _document_projection()))
    docs_processed = len(changed_docs)
    removed_ids = list(removed_doc_ids or [])
    if not changed_docs and not removed_ids:
        source_stats = _load_source_stats(source_stats_col)
        return {
            "total_docs_processed": 0,
            "docs_processed": 0,
            "removed_docs_processed": 0,
            "unique_words": int(source_totals_col.count_documents({})),
            "entries_stored": int(freq_col.count_documents({})),
            "sources": sorted(source_stats),
            "nayiri_headwords": 0,
            "last_enrichment_date": None,
            "touched_words": 0,
            **_resolve_weight_info(source_stats, config),
        }

    touched_words: set[str] = set()
    touched_sources: set[str] = set()
    last_enrichment_date: str | None = None
    removed_processed = 0

    for doc in changed_docs:
        new_state = _build_document_state(doc)
        old_state = doc_state_col.find_one({"_id": new_state["_id"]})
        _apply_document_delta(
            source_totals_col,
            source_stats_col,
            old_state,
            new_state,
            touched_words,
            touched_sources,
        )
        doc_state_col.replace_one({"_id": new_state["_id"]}, new_state, upsert=True)
        last_enrichment_date = _max_enrichment_date(
            last_enrichment_date,
            new_state.get("enrichment_date"),
        )

    for doc_id in removed_ids:
        old_state = doc_state_col.find_one({"_id": doc_id})
        if old_state is None:
            continue
        _remove_document_state(
            source_totals_col,
            source_stats_col,
            old_state,
            touched_words,
            touched_sources,
        )
        doc_state_col.delete_one({"_id": doc_id})
        removed_processed += 1

    _cleanup_source_totals(source_totals_col, touched_words)
    _cleanup_source_stats(source_stats_col, touched_sources)

    source_stats = _load_source_stats(source_stats_col)
    weight_info = _resolve_weight_info(source_stats, config)
    entries, unique_words = _build_materialized_entries(
        source_totals_col.find({}, {"word": 1, "source_counts": 1, "nayiri_headword_count": 1}),
        weight_info["weight_map"],
    )
    _replace_materialized_collection(freq_col, entries)

    return {
        "total_docs_processed": docs_processed + removed_processed,
        "docs_processed": docs_processed,
        "removed_docs_processed": removed_processed,
        "unique_words": unique_words,
        "entries_stored": len(entries),
        "sources": sorted(source_stats),
        "nayiri_headwords": 0,
        "last_enrichment_date": last_enrichment_date,
        "touched_words": len(touched_words),
        **weight_info,
    }


def run(config: dict) -> None:
    from hytools.ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB is required for frequency aggregation")

        query = _build_docs_query(config)
        query_signature = _query_signature(query)
        incremental = bool(_get_frequency_config(config).get("incremental", False))

        if incremental:
            summary = run_incremental_update(client, config, query)
        else:
            summary = _run_full_rebuild(client, config)

        client.metadata.replace_one(
            {"stage": "frequency_aggregator"},
            _build_frequency_metadata_doc("frequency_aggregator", summary, query_signature),
            upsert=True,
        )

        print(
            f"Frequency list: {summary['entries_stored']} words from {summary['total_docs_processed']} documents"
        )
        print(f"Sources: {summary['sources']}")
        if summary.get("target_pcts"):
            print("Weights: target-weighted")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run({})
