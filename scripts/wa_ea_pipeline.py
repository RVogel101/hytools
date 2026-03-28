#!/usr/bin/env python
"""End-to-end WA vs EA analysis runner: samples corpora, runs metrics, outputs JSON and plots."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
from pathlib import Path
from typing import List, Tuple

from hytools.linguistics.orthography.reform_classical_converter import (
    orthography_score,
    to_reformed,
)
from hytools.linguistics.phonology.utils import (
    split_sentences,
    align_sentences,
    phonetic_transcription,
    aggregate_numeric,
)

from hytools.config.settings import load_config
from hytools.ingestion._shared.helpers import open_mongodb_client
from hytools.cleaning.armenian_tokenizer import extract_words

try:
    import matplotlib.pyplot as plt
except Exception:
    plt = None


def load_script_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sample_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _build_lang_query(lang_tag: str, source_filter: str | None = None) -> dict:
    # Use only the canonical internal tag for filtering: metadata.internal_language_branch
    query = {"metadata.internal_language_branch": lang_tag}
    if source_filter:
        query = {"$and": [query, {"source": source_filter}]}
    return query


def _truncate_to_token_count(text: str, n_tokens: int) -> str:
    """Sentence-preserving truncation up to n_tokens.

    Prefer to include whole sentences until token budget exhausted. If the
    first sentence alone exceeds the budget, fallback to token-level truncation
    within that first sentence.
    """
    if n_tokens <= 0:
        return ""

    sents = split_sentences(text)
    out_sents = []
    used = 0
    for s in sents:
        toks = extract_words(s, min_length=1)
        if used + len(toks) <= n_tokens:
            out_sents.append(s)
            used += len(toks)
        else:
            # if nothing selected yet and this sentence is too long, truncate sentence
            if used == 0:
                if len(toks) == 0:
                    return ""
                return " ".join(toks[:n_tokens])
            break

    if out_sents:
        return " ".join(out_sents)
    return ""


def sample_matched_pairs_from_mongodb(
    config_path: str,
    n_pairs: int = 10,
    pool_multiplier: int = 8,
    wa_tag: str = "hye-w",
    ea_tag: str = "hye-e",
    source_filter: str | None = None,
) -> List[Tuple[str, str]]:
    cfg = load_config(config_path)
    with open_mongodb_client(cfg) as client:
        if client is None:
            raise RuntimeError("MongoDB client unavailable. Check config and pymongo installation.")

        wa_q = _build_lang_query(wa_tag, source_filter=source_filter)
        ea_q = _build_lang_query(ea_tag, source_filter=source_filter)

        wa_cursor = client.documents.find(wa_q).limit(n_pairs * pool_multiplier)
        ea_cursor = client.documents.find(ea_q).limit(n_pairs * pool_multiplier)

        wa_docs = []
        ea_docs = []

        for d in wa_cursor:
            text = d.get("text", "")
            toks = len(extract_words(text, min_length=1))
            wa_docs.append({"text": text, "tokens": toks, "id": str(d.get("_id"))})

        for d in ea_cursor:
            text = d.get("text", "")
            toks = len(extract_words(text, min_length=1))
            ea_docs.append({"text": text, "tokens": toks, "id": str(d.get("_id"))})

        if not wa_docs or not ea_docs:
            raise RuntimeError("Not enough WA or EA documents found in MongoDB for sampling.")

        # sort by token count
        wa_docs.sort(key=lambda x: x["tokens"])
        ea_docs.sort(key=lambda x: x["tokens"])

        pairs: List[Tuple[str, str]] = []
        used_ea = set()

        # greedy nearest-neighbour pairing
        for wa in wa_docs:
            best = None
            best_diff = None
            for idx, ea in enumerate(ea_docs):
                if idx in used_ea:
                    continue
                diff = abs(ea["tokens"] - wa["tokens"])
                if best is None or diff < best_diff:
                    best = (idx, ea)
                    best_diff = diff
            if best is None:
                continue
            idx, ea_choice = best
            used_ea.add(idx)

            # equalize token counts by truncating to minimum (sentence-preserving)
            min_tokens = min(wa["tokens"], ea_choice["tokens"]) or 0
            a_text = _truncate_to_token_count(wa["text"], min_tokens)
            b_text = _truncate_to_token_count(ea_choice["text"], min_tokens)
            pairs.append((a_text, b_text))
            if len(pairs) >= n_pairs:
                break

        return pairs


def run_pair(wa_text: str, ea_text: str, compute_all_func) -> dict:
    # Sentence align
    wa_sents = split_sentences(wa_text)
    ea_sents = split_sentences(ea_text)
    pairs = align_sentences(wa_sents, ea_sents)

    phon_dists = []
    orth_scores = []

    for a, b in pairs:
        # phonetic
        pa = phonetic_transcription(a, dialect="hye-w")
        pb = phonetic_transcription(b, dialect="hye-e")
        # compute edit on phonetic strings using compute_all_func (char metric)
        metrics = compute_all_func(pa, pb)
        phon_dists.append(metrics.get("normalized_edit_distance", 0.0))

        # orthography score on source texts
        orth_scores.append(orthography_score(a))
        orth_scores.append(orthography_score(b))

    phon_stats = aggregate_numeric(phon_dists)
    orth_stats = aggregate_numeric(orth_scores)

    # Lexical/other metrics via compute_all on full texts
    full_metrics = compute_all_func(wa_text, ea_text)

    return {
        "phonetic": phon_stats,
        "phonetic_list": phon_dists,
        "orthographic": orth_stats,
        "orthographic_list": orth_scores,
        "lexical_full": full_metrics,
    }


def main():
    parser = argparse.ArgumentParser(description="Run WA/EA end-to-end pipeline")
    parser.add_argument("--wa", help="Western Armenian text file")
    parser.add_argument("--ea", help="Eastern Armenian text file")
    parser.add_argument("--from-mongodb", action="store_true", help="Sample pairs from MongoDB instead of files")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to config YAML (for MongoDB)")
    parser.add_argument("--wa-tag", default="hye-w", help="Metadata tag to identify WA documents (default: hye-w)")
    parser.add_argument("--ea-tag", default="hye-e", help="Metadata tag to identify EA documents (default: hye-e)")
    parser.add_argument("--source-filter", default=None, help="Optional source filter (e.g. newspaper:aztag)")
    parser.add_argument("--sample-size", type=int, default=10, help="Number of pairs to sample from MongoDB")
    parser.add_argument("--pool-multiplier", type=int, default=8, help="Candidate pool multiplier when sampling from MongoDB")
    parser.add_argument("--outdir", default="analysis/wa_ea_pipeline", help="Output directory")
    parser.add_argument("--plot", action="store_true", help="Generate simple matplotlib plots (requires matplotlib)")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # Load compute_distances from scripts
    compute_path = Path("scripts/compute_distances.py").resolve()
    mod = load_script_module(str(compute_path), "compute_distances")
    compute_all = getattr(mod, "compute_all")

    pairs = []
    if args.from_mongodb:
        pairs = sample_matched_pairs_from_mongodb(
            args.config,
            n_pairs=args.sample_size,
            pool_multiplier=args.pool_multiplier,
            wa_tag=args.wa_tag,
            ea_tag=args.ea_tag,
            source_filter=args.source_filter,
        )
    else:
        if not args.wa or not args.ea:
            parser.error("When not using --from-mongodb, --wa and --ea file paths are required")
        wa_text = sample_text_file(args.wa)
        ea_text = sample_text_file(args.ea)
        pairs = [(wa_text, ea_text)]

    summaries = []
    for idx, (wa_text, ea_text) in enumerate(pairs, start=1):
        try:
            summary = run_pair(wa_text, ea_text, compute_all)
            summary["pair_index"] = idx
            summaries.append(summary)
        except Exception as exc:
            print(f"Failed on pair {idx}: {exc}")

    # write JSON summary
    out_json = Path(args.outdir) / "wa_ea_pipeline_summary.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"pairs": summaries}, f, ensure_ascii=False, indent=2)
    print("Wrote summary to", out_json)

    # Optionally save to MongoDB augmentation_metrics
    if args.from_mongodb:
        batch_id = f"wa_ea_pipeline::{os.environ.get('USERNAME','user')}::{__import__('uuid').uuid4()}"
        report = {
            "batch_id": batch_id,
            "generated_by": "wa_ea_pipeline",
            "pair_count": len(summaries),
            "pairs": summaries,
        }
        try:
            cfg = load_config(args.config)
            with open_mongodb_client(cfg) as client:
                if client is None:
                    print("MongoDB client unavailable; skipping saving to DB")
                else:
                    client.insert_augmentation_metrics_report(batch_id, "wa_ea_distance", report)
                    print("Inserted batch report into MongoDB augmentation_metrics (batch_id=", batch_id, ")")
        except Exception as exc:
            print("Failed to save summary to MongoDB:", exc)

    # plotting: prefer plotly for interactivity when available, else matplotlib
    if args.plot:
        try:
            import plotly.express as px
            import pandas as pd
            # prepare pair-level table
            rows = []
            for p in summaries:
                rows.append({
                    "pair_index": p.get("pair_index"),
                    "phonetic_mean": p.get("phonetic", {}).get("mean"),
                    "orthographic_mean": p.get("orthographic", {}).get("mean"),
                })
            df = pd.DataFrame(rows)
            if not df.empty:
                fig1 = px.scatter(df, x="phonetic_mean", y="orthographic_mean", hover_data=["pair_index"], title="Phonetic vs Orthographic mean per pair")
                fig1.write_image(str(Path(args.outdir) / "wa_ea_scatter.png"))
                fig1.write_html(str(Path(args.outdir) / "wa_ea_scatter.html"))

                # boxplot of phonetic per-sentence lists (flattened into a dataframe)
                flat_rows = []
                for p in summaries:
                    for v in p.get("phonetic_list", []):
                        flat_rows.append({"pair_index": p.get("pair_index"), "phonetic_distance": v})
                if flat_rows:
                    dff = pd.DataFrame(flat_rows)
                    fig2 = px.box(dff, x="pair_index", y="phonetic_distance", title="Per-sentence phonetic distances by pair")
                    fig2.write_image(str(Path(args.outdir) / "wa_ea_phonetic_box.png"))
                    fig2.write_html(str(Path(args.outdir) / "wa_ea_phonetic_box.html"))

                print("Wrote interactive plots to", args.outdir)
        except Exception:
            # fallback to matplotlib simple images
            if plt is None:
                print("Plotting libraries not available; install plotly/pandas or matplotlib to enable plotting")
            else:
                phon_means = [p["phonetic"]["mean"] for p in summaries if p.get("phonetic")]
                ortho_means = [p["orthographic"]["mean"] for p in summaries if p.get("orthographic")]
                fig, ax = plt.subplots(1, 2, figsize=(10, 4))
                ax[0].bar(range(1, len(phon_means) + 1), phon_means)
                ax[0].set_title("Phonetic mean per pair")
                ax[0].set_xlabel("pair_index")
                ax[0].set_ylabel("mean phonetic distance")
                ax[1].bar(range(1, len(ortho_means) + 1), ortho_means)
                ax[1].set_title("Orthographic mean per pair")
                ax[1].set_xlabel("pair_index")
                ax[1].set_ylabel("orthography score")
                plot_path = Path(args.outdir) / "wa_ea_pipeline_plots.png"
                fig.tight_layout()
                fig.savefig(plot_path)
                print("Wrote plots to", plot_path)


if __name__ == "__main__":
    main()
