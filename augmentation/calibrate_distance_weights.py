"""Calibrate component weights for WA/EA distance separation.

Performs random search over weight space and optimizes the objective:
    separation_margin = avg_inter_dialect_distance - avg_intra_dialect_distance

Outputs best weights and top candidates for reproducible scoring.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from augmentation.benchmark_dialect_distance import _read_texts, _score_config
from linguistics.dialect.dialect_distance import DistanceWeights


def _sample_simplex4(rng: random.Random) -> dict[str, float]:
    vals = [rng.random() for _ in range(5)]
    s = sum(vals) or 1.0
    vals = [v / s for v in vals]
    keys = [
        "js_divergence",
        "weighted_jaccard_distance",
        "mapping_shift_rate",
        "variant_usage_rate_distance",
        "keyword_context_js",
    ]
    return dict(zip(keys, vals))


def _sample_simplex2(rng: random.Random) -> dict[str, float]:
    a = rng.random()
    return {
        "sentence_length_wasserstein": a,
        "function_bigram_js": 1.0 - a,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m augmentation.calibrate_distance_weights",
        description="Calibrate component weights for dialect distance scoring.",
    )
    parser.add_argument("--wa-dirs", nargs="+", required=True)
    parser.add_argument("--ea-dirs", nargs="+", required=True)
    parser.add_argument("--mapping", default="cache/west_east_usage_mapping.json")
    parser.add_argument(
        "--variant-pairs-json",
        default="",
        help="Optional JSON file with explicit variant pairs: [[western,eastern], ...]",
    )
    parser.add_argument(
        "--contextual-keywords-json",
        default="",
        help="Optional JSON file with shared keywords for context divergence: [word1, word2, ...]",
    )
    parser.add_argument("--max-files", type=int, default=2000)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--search-iters", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="cache/dialect_distance_calibration.json")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    wa_texts = _read_texts(args.wa_dirs, max_files=args.max_files, seed=args.seed)
    ea_texts = _read_texts(args.ea_dirs, max_files=args.max_files, seed=args.seed + 1)

    if len(wa_texts) < 2 or len(ea_texts) < 2:
        raise SystemExit("Need at least 2 WA texts and 2 EA texts for calibration.")

    mapping: dict[str, dict] = {}
    mapping_path = Path(args.mapping)
    if mapping_path.exists():
        mapping = json.loads(mapping_path.read_text(encoding="utf-8"))

    variant_pairs = [
        (str(meta.get("canonical_western_form", "")).strip(), ea)
        for ea, meta in mapping.items()
        if str(meta.get("canonical_western_form", "")).strip()
    ]

    if args.variant_pairs_json:
        vp_path = Path(args.variant_pairs_json)
        if vp_path.exists():
            raw_pairs = json.loads(vp_path.read_text(encoding="utf-8"))
            for pair in raw_pairs:
                if isinstance(pair, list) and len(pair) == 2:
                    west_form = str(pair[0]).strip()
                    east_form = str(pair[1]).strip()
                    if west_form and east_form:
                        variant_pairs.append((west_form, east_form))

    seen: set[tuple[str, str]] = set()
    deduped: list[tuple[str, str]] = []
    for p in variant_pairs:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    variant_pairs = deduped

    contextual_keywords: list[str] = []
    if args.contextual_keywords_json:
        ck_path = Path(args.contextual_keywords_json)
        if ck_path.exists():
            raw_keywords = json.loads(ck_path.read_text(encoding="utf-8"))
            contextual_keywords = [str(w).strip() for w in raw_keywords if str(w).strip()]

    function_words = {
        "կը",
        "պիտի",
        "հոն",
        "հոս",
        "ու",
        "ալ",
        "որ",
        "չեմ",
        "չէ",
    }

    best_score = float("-inf")
    best_cfg: DistanceWeights | None = None
    leaderboard: list[dict] = []

    for _ in range(args.search_iters):
        lexical_weight = 0.45 + 0.45 * rng.random()  # [0.45, 0.90]
        structural_weight = 1.0 - lexical_weight

        cfg = DistanceWeights(
            lexical_weight=lexical_weight,
            structural_weight=structural_weight,
            lexical_subweights=_sample_simplex4(rng),
            structural_subweights=_sample_simplex2(rng),
        )

        score = _score_config(
            wa_texts,
            ea_texts,
            cfg,
            mapping,
            variant_pairs,
            contextual_keywords,
            function_words,
            trials=args.trials,
            seed=args.seed,
        )

        entry = {
            "separation_margin": score["separation_margin"],
            "avg_inter_distance": score["avg_inter_distance"],
            "avg_intra_distance": score["avg_intra_distance"],
            "weights": {
                "lexical_weight": cfg.lexical_weight,
                "structural_weight": cfg.structural_weight,
                "lexical_subweights": cfg.lexical_subweights,
                "structural_subweights": cfg.structural_subweights,
            },
        }
        leaderboard.append(entry)

        if score["separation_margin"] > best_score:
            best_score = score["separation_margin"]
            best_cfg = cfg

    leaderboard.sort(key=lambda x: x["separation_margin"], reverse=True)
    top10 = leaderboard[:10]

    payload = {
        "meta": {
            "wa_docs": len(wa_texts),
            "ea_docs": len(ea_texts),
            "trials": args.trials,
            "search_iterations": args.search_iters,
            "mapping_pairs": len(variant_pairs),
            "contextual_keywords": len(contextual_keywords),
        },
        "best": top10[0] if top10 else None,
        "top_candidates": top10,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("Dialect weight calibration completed.")
    print(f"Output: {out_path}")
    if best_cfg is not None:
        print(f"Best separation margin: {best_score:.4f}")
        print(
            "Best top-level weights: "
            f"lexical={best_cfg.lexical_weight:.3f}, "
            f"structural={best_cfg.structural_weight:.3f}"
        )


if __name__ == "__main__":
    main()
