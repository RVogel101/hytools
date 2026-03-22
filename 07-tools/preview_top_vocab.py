"""Preview top N vocabulary items from MongoDB `word_frequencies` with metadata.

Usage:
    python 07-tools/preview_top_vocab.py --limit 10

Outputs columns: rank, word, total_count, difficulty, phonetic_score, orthographic_score,
and card-side metadata if available (syllable_count, pos, translation).
"""
from __future__ import annotations

import argparse
from hytool.ingestion._shared.helpers import open_mongodb_client


def run(limit: int = 10, config: dict | None = None) -> None:
    with open_mongodb_client(config or {}) as client:
        if client is None:
            raise RuntimeError("MongoDB required")
        db = client.db
        freq_col = db.get_collection("word_frequencies")
        cards_col = db.get_collection("cards")

        cursor = freq_col.find({}, sort=[("rank", 1)], limit=limit)
        rows = []
        for doc in cursor:
            word = doc.get("word")
            row = {
                "rank": doc.get("rank"),
                "word": word,
                "total_count": doc.get("total_count"),
                "difficulty": doc.get("difficulty"),
                "phonetic_score": doc.get("phonetic_score"),
                "orthographic_score": doc.get("orthographic_score"),
                "composite_score": doc.get("composite_score"),
                "used_aggregate": doc.get("used_aggregate"),
            }

            # Try to pull matching card metadata
            card = cards_col.find_one({"word": word}) or cards_col.find_one({"front": word}) or cards_col.find_one({"fields.0": word})
            if card:
                row.update({
                    "syllable_count": card.get("syllable_count"),
                    "pos": card.get("pos"),
                    "translation": card.get("translation"),
                })
            rows.append(row)

        # Print a simple table
        headers = ["rank", "word", "total_count", "difficulty", "phonetic", "ortho", "composite", "syllables", "pos", "translation"]
        print("\t".join(headers))
        for r in rows:
            print("\t".join([str(r.get(h, "")) for h in headers]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Preview top vocabulary from MongoDB")
    parser.add_argument("--limit", type=int, default=10, help="Number of top words to show")
    parser.add_argument("--config", type=str, default=None, help="Optional YAML config path")
    args = parser.parse_args()

    cfg = None
    if args.config:
        import yaml
        with open(args.config, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}

    run(limit=args.limit, config=cfg)

