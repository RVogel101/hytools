#!/usr/bin/env python
"""Run the new hytools cleaning pipeline in stages."""
from __future__ import annotations

import argparse
import json
import os
import sys

from hytools.cleaning.pipeline import create_clean_corpus
from hytools.config.settings import load_config
from hytools.ingestion._shared.helpers import open_mongodb_client, get_lexical_markers
from hytools.linguistics import get_phonetic_transcription, calculate_phonetic_difficulty
from hytools.linguistics.metrics.text_metrics import compute_orthographic_metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Run hytools data pipeline")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to config file")
    parser.add_argument("--output", default="data/cleaned_corpus", help="Output path for cleaned corpus")
    parser.add_argument("--source-collection", default="documents", help="MongoDB source collection")
    parser.add_argument("--output-collection", default="documents_cleaned", help="MongoDB staging collection")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    cfg = load_config(args.config)
    summary = create_clean_corpus(
        config=cfg,
        source_collection=args.source_collection,
        output_collection=args.output_collection,
        output_path=args.output,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def prepare_corpus(config_path: str):
    """Prepare the corpus by validating and extracting data from MongoDB."""
    import json

    with open(config_path, "r") as f:
        config = json.load(f)

    with open_mongodb_client(config) as client:
        if client is None:
            print("Failed to connect to MongoDB. Check your configuration.")
            return

        # Example: Count documents by source
        coll = client.db["documents"]
        print("Source counts:")
        for doc in coll.aggregate([
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]):
            print(doc)

        # Example: Count documents by language branch
        print("Language branch counts:")
        for doc in coll.aggregate([
            {"$group": {"_id": "$metadata.language_branch", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]):
            print(doc)


def compute_phonetic_distance(text_wa: str, text_ea: str):
    """Compute phonetic distance between WA and EA texts."""
    transcription_wa = get_phonetic_transcription(text_wa)
    transcription_ea = get_phonetic_transcription(text_ea)

    # Example metric: Edit distance between transcriptions
    from nltk.metrics.distance import edit_distance
    distance = edit_distance(transcription_wa, transcription_ea)

    # Example metric: Phonetic difficulty comparison
    difficulty_wa = calculate_phonetic_difficulty(transcription_wa)
    difficulty_ea = calculate_phonetic_difficulty(transcription_ea)

    return {
        "edit_distance": distance,
        "difficulty_wa": difficulty_wa,
        "difficulty_ea": difficulty_ea,
    }


def compute_lexical_distance(text_wa: str, text_ea: str):
    """Compute lexical distance between WA and EA texts."""
    lexical_markers = get_lexical_markers()

    # Example metric: Count WA-specific markers in both texts
    wa_count = sum(1 for marker, _ in lexical_markers if marker in text_wa)
    ea_count = sum(1 for marker, _ in lexical_markers if marker in text_ea)

    # Example metric: Ratio of WA markers to total markers
    total_count = wa_count + ea_count
    wa_ratio = wa_count / total_count if total_count > 0 else 0

    return {
        "wa_count": wa_count,
        "ea_count": ea_count,
        "wa_ratio": wa_ratio,
    }


def compute_orthographic_distance(text_wa: str, text_ea: str):
    """Compute orthographic distance between WA and EA texts."""
    orthographic_metrics_wa = compute_orthographic_metrics(text_wa)
    orthographic_metrics_ea = compute_orthographic_metrics(text_ea)

    return {
        "classical_markers_wa": orthographic_metrics_wa.classical_markers_count,
        "reformed_markers_wa": orthographic_metrics_wa.reformed_markers_count,
        "classical_to_reformed_ratio_wa": orthographic_metrics_wa.classical_to_reformed_ratio,
        "classical_markers_ea": orthographic_metrics_ea.classical_markers_count,
        "reformed_markers_ea": orthographic_metrics_ea.reformed_markers_count,
        "classical_to_reformed_ratio_ea": orthographic_metrics_ea.classical_to_reformed_ratio,
    }


def calculate_composite_distance(phonetic: dict, lexical: dict, orthographic: dict):
    """Calculate a composite distance index from individual metrics."""
    weights = {
        "phonetic": 0.4,
        "lexical": 0.3,
        "orthographic": 0.3,
    }

    composite_index = (
        weights["phonetic"] * phonetic["edit_distance"] +
        weights["lexical"] * lexical["wa_ratio"] +
        weights["orthographic"] * (
            orthographic["classical_to_reformed_ratio_wa"] +
            orthographic["classical_to_reformed_ratio_ea"]
        ) / 2
    )

    return {
        "composite_distance_index": composite_index,
    }


def benchmark_distance_metrics(composite_index: float):
    """Benchmark the composite distance index against predefined thresholds."""
    benchmarks = {
        "low": 0.2,
        "medium": 0.5,
        "high": 0.8,
    }

    if composite_index < benchmarks["low"]:
        level = "Low"
    elif composite_index < benchmarks["medium"]:
        level = "Medium"
    elif composite_index < benchmarks["high"]:
        level = "High"
    else:
        level = "Very High"

    return {
        "composite_index": composite_index,
        "benchmark_level": level,
    }


def check_documents_language_tags(config_path: str):
    """Check if documents contain specific internal_language_branch tags."""
    import json

    with open(config_path, "r") as f:
        config = json.load(f)

    with open_mongodb_client(config) as client:
        if client is None:
            print("Failed to connect to MongoDB. Check your configuration.")
            return

        coll = client.db["documents"]

        # Check for Western Armenian (hye-w)
        wa_count = coll.count_documents({"metadata.internal_language_branch": "hye-w"})
        print(f"Western Armenian documents (hye-w): {wa_count}")

        # Check for Eastern Armenian (hye-e)
        ea_count = coll.count_documents({"metadata.internal_language_branch": "hye-e"})
        print(f"Eastern Armenian documents (hye-e): {ea_count}")


if __name__ == "__main__":
    main()
