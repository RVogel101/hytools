#!/usr/bin/env python
"""Run pairwise comparisons across multiple language tags using the WA/EA pipeline.

This loads `scripts/wa_ea_pipeline.py` functions (sampling + run_pair) and
`scripts/compute_distances.py::compute_all` then computes metrics for every
ordered tag pair and emits JSON summaries and heatmap visualizations.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
from itertools import product
from pathlib import Path
from typing import List


def load_script_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def mean_or_none(values: List[float]):
    if not values:
        return None
    return sum(values) / len(values)


def main():
    parser = argparse.ArgumentParser(description="Pairwise runner for WA/EA pipeline")
    parser.add_argument("--tags", help="Comma-separated list of metadata.internal_language_branch tags (e.g. hye-w,hye-e,ru)")
    parser.add_argument("--from-mongodb", action="store_true", help="Sample from MongoDB for each tag pair")
    parser.add_argument("--config", default="config/settings.yaml", help="Path to config YAML for MongoDB access")
    parser.add_argument("--sample-size", type=int, default=10, help="Number of pairs per tag-pair to sample")
    parser.add_argument("--pool-multiplier", type=int, default=8, help="Candidate pool multiplier when sampling from MongoDB")
    parser.add_argument("--outdir", default="analysis/wa_ea_pipeline/pairwise", help="Output directory to write summaries and plots")
    parser.add_argument("--plot", action="store_true", help="Generate heatmap plots (requires plotly/pandas or matplotlib)")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # Load existing pipeline helpers
    wa_mod = load_script_module(str(Path("scripts/wa_ea_pipeline.py").resolve()), "wa_ea_pipeline")
    compute_mod = load_script_module(str(Path("scripts/compute_distances.py").resolve()), "compute_distances")
    compute_all = getattr(compute_mod, "compute_all")

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    if not tags:
        parser.error("--tags must be provided with at least one tag")

    results = {}

    # iterate ordered pairs (including same-tag comparisons)
    for a, b in product(tags, tags):
        key = f"{a}__vs__{b}"
        print("Processing", key)
        pair_summaries = []
        def tokenize_count(s: str):
            toks = re.findall(r"\w+", s)
            return len(toks)

        def load_ext_segments(tag: str, n_segments: int):
            # load content from MongoDB external_datasets collection for this tag
            try:
                import sys
                from pathlib import Path as _Path
                _scripts_dir = str(_Path(__file__).resolve().parent)
                if _scripts_dir not in sys.path:
                    sys.path.insert(0, _scripts_dir)
                from external_db import fetch_external_tag
            except Exception:
                print("MongoDB helper not available; ensure scripts/external_db.py exists")
                return []
            recs = fetch_external_tag(tag, limit=n_segments * args.pool_multiplier, config_path=args.config)
            texts = [r.get("content", "") for r in recs if r.get("content")]
            if not texts:
                return []
            # tokenize and split across concatenated texts until we have n_segments
            toks = []
            for t in texts:
                toks.extend(re.findall(r"\w+", t))
            if not toks:
                return []
            chunk_size = max(1, len(toks) // n_segments)
            segments = []
            for i in range(0, len(toks), chunk_size):
                seg = " ".join(toks[i : i + chunk_size])
                segments.append({"text": seg, "tokens": len(re.findall(r"\w+", seg))})
                if len(segments) >= n_segments:
                    break
            return segments

        # three cases: both non-ext -> use existing sampler that returns paired texts
        if not a.startswith("ext:") and not b.startswith("ext:") and args.from_mongodb:
            try:
                pairs = wa_mod.sample_matched_pairs_from_mongodb(
                    args.config,
                    n_pairs=args.sample_size,
                    pool_multiplier=args.pool_multiplier,
                    wa_tag=a,
                    ea_tag=b,
                )
            except Exception as exc:
                print(f"Sampling failed for {key}: {exc}")
                pairs = []

        else:
            # support external tags
            # produce candidate document lists for a and b
            def candidates_for(tag: str):
                if tag.startswith("ext:"):
                    return load_ext_segments(tag, args.sample_size * args.pool_multiplier)
                else:
                    # sample from mongodb by sampling same-tag pairs and flattening
                    try:
                        raw_pairs = wa_mod.sample_matched_pairs_from_mongodb(
                            args.config,
                            n_pairs=args.sample_size * args.pool_multiplier,
                            pool_multiplier=1,
                            wa_tag=tag,
                            ea_tag=tag,
                        )
                    except Exception as exc:
                        print(f"Failed to sample candidates for {tag}: {exc}")
                        return []
                    docs = []
                    for x, y in raw_pairs:
                        docs.append({"text": x, "tokens": tokenize_count(x)})
                        docs.append({"text": y, "tokens": tokenize_count(y)})
                    # deduplicate by text
                    seen = set()
                    out = []
                    for d in docs:
                        t = d["text"]
                        if t in seen:
                            continue
                        seen.add(t)
                        out.append(d)
                    return out

            cand_a = candidates_for(a)
            cand_b = candidates_for(b)

            # greedy nearest-token pairing
            pairs = []
            used_b = set()
            for da in cand_a:
                best = None
                best_diff = None
                for idx, db in enumerate(cand_b):
                    if idx in used_b:
                        continue
                    diff = abs(db["tokens"] - da["tokens"])
                    if best is None or diff < best_diff:
                        best = (idx, db)
                        best_diff = diff
                if best is None:
                    continue
                idx, db_choice = best
                used_b.add(idx)
                # equalize
                min_tokens = min(da["tokens"], db_choice["tokens"]) or 0
                a_text = " ".join(re.findall(r"\w+", da["text"])[:min_tokens])
                b_text = " ".join(re.findall(r"\w+", db_choice["text"])[:min_tokens])
                pairs.append((a_text, b_text))
                if len(pairs) >= args.sample_size:
                    break


        for wa_text, ea_text in pairs:
            try:
                summary = wa_mod.run_pair(wa_text, ea_text, compute_all)
                pair_summaries.append(summary)
            except Exception as exc:
                print(f"run_pair failed for {key}: {exc}")

        # aggregate numeric means across sampled pairs
        phon_means = [s.get("phonetic", {}).get("mean") for s in pair_summaries if s.get("phonetic")]
        ortho_means = [s.get("orthographic", {}).get("mean") for s in pair_summaries if s.get("orthographic")]
        # lexical: try to extract normalized_edit_distance from lexical_full
        lex_vals = []
        for s in pair_summaries:
            lf = s.get("lexical_full", {})
            if isinstance(lf, dict) and lf.get("normalized_edit_distance") is not None:
                lex_vals.append(lf.get("normalized_edit_distance"))

        results[key] = {
            "a": a,
            "b": b,
            "n_pairs": len(pair_summaries),
            "phonetic_mean": mean_or_none([v for v in phon_means if v is not None]),
            "orthographic_mean": mean_or_none([v for v in ortho_means if v is not None]),
            "lexical_mean": mean_or_none([v for v in lex_vals if v is not None]),
            "pairs": pair_summaries,
        }

    # write JSON
    out_json = Path(args.outdir) / "pairwise_summary.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"tags": tags, "results": results}, f, ensure_ascii=False, indent=2)
    print("Wrote pairwise summary to", out_json)

    if args.plot:
        try:
            import pandas as pd
            import plotly.express as px

            # build matrices
            phon_mat = []
            ortho_mat = []
            lex_mat = []
            for a in tags:
                row_p = []
                row_o = []
                row_l = []
                for b in tags:
                    key = f"{a}__vs__{b}"
                    r = results.get(key, {})
                    row_p.append(r.get("phonetic_mean"))
                    row_o.append(r.get("orthographic_mean"))
                    row_l.append(r.get("lexical_mean"))
                phon_mat.append(row_p)
                ortho_mat.append(row_o)
                lex_mat.append(row_l)

            df_phon = pd.DataFrame(phon_mat, index=tags, columns=tags)
            df_ortho = pd.DataFrame(ortho_mat, index=tags, columns=tags)
            df_lex = pd.DataFrame(lex_mat, index=tags, columns=tags)

            def save_heat(df, name):
                fig = px.imshow(df, text_auto=True, aspect="auto", title=name)
                fig.write_html(str(Path(args.outdir) / f"{name.replace(' ', '_').lower()}.html"))
                fig.write_image(str(Path(args.outdir) / f"{name.replace(' ', '_').lower()}.png"))

            save_heat(df_phon, "Phonetic Mean")
            save_heat(df_ortho, "Orthographic Mean")
            save_heat(df_lex, "Lexical Mean")

            print("Wrote heatmaps to", args.outdir)
        except Exception:
            try:
                import matplotlib.pyplot as plt
                import numpy as np

                def save_mat(mat, name):
                    plt.figure(figsize=(6, 4))
                    plt.imshow(np.array(mat, dtype=float), cmap="viridis", interpolation="nearest")
                    plt.colorbar()
                    plt.xticks(range(len(tags)), tags, rotation=45)
                    plt.yticks(range(len(tags)), tags)
                    plt.title(name)
                    plt.tight_layout()
                    plt.savefig(Path(args.outdir) / f"{name.replace(' ', '_').lower()}.png")

                save_mat(phon_mat, "Phonetic Mean")
                save_mat(ortho_mat, "Orthographic Mean")
                save_mat(lex_mat, "Lexical Mean")
                print("Wrote fallback matplotlib heatmaps to", args.outdir)
            except Exception:
                print("Plot libraries unavailable; skip plotting")


if __name__ == "__main__":
    main()
