"""Dialect subcategory feature extraction and clustering (PCA + DBSCAN).

This module is designed for exploratory language-distance analysis across
fine-grained Armenian subcategories (e.g., arm eno_turkish, eastern_hayastan,
eastern_russian_influence, eastern_iran).

Workflow:
1. Read metadata JSONL files from corpus
2. Build numeric feature vectors from text statistics + metadata-derived signals
3. Run PCA to 2D or 3D for visualization coordinates
4. Run DBSCAN for unsupervised cluster labels
5. Write outputs for downstream plotting or analysis notebooks
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from armenian_corpus_core.cleaning.armenian_tokenizer import extract_words


def _safe_log_ratio(num: float, den: float) -> float:
    """Compute log ratio with smoothing for numerical stability."""
    return math.log((num + 1e-8) / (den + 1e-8))


def _count_suffix(tokens: list[str], suffix: str) -> int:
    return sum(1 for t in tokens if t.endswith(suffix))


def _armenian_char_count(text: str) -> int:
    return sum(1 for ch in text if "\u0530" <= ch <= "\u058F")


def _sentence_split(text: str) -> list[str]:
    parts = []
    current = []
    for ch in text:
        current.append(ch)
        if ch in ".!?։":
            sent = "".join(current).strip()
            if sent:
                parts.append(sent)
            current = []
    if current:
        sent = "".join(current).strip()
        if sent:
            parts.append(sent)
    return parts


@dataclass
class FeatureRow:
    text_file: str
    source_name: str
    dialect: str
    dialect_subcategory: str
    language_code: str
    region: str
    feature_vector: list[float]


def _build_feature_vector(text: str) -> list[float]:
    """Build numeric feature vector for clustering axes.

    Feature order:
    1) log token_count
    2) type_token_ratio
    3) avg_sentence_length
    4) em_rate (-եմ)
    5) im_rate (-իմ)
    6) em_vs_im_log_ratio
    7) armenian_char_ratio
    8) punctuation_rate
    9) classical_marker_rate (իւ/եա)
    10) hyastan_marker_rate (-ություն / -ութիւն proxy)
    """
    tokens = extract_words(text, min_length=2)
    token_count = len(tokens)
    unique_count = len(set(tokens))
    ttr = (unique_count / token_count) if token_count else 0.0

    sentences = _sentence_split(text)
    sentence_lengths = [len(extract_words(s, min_length=1)) for s in sentences if s.strip()]
    avg_sentence_len = (sum(sentence_lengths) / len(sentence_lengths)) if sentence_lengths else 0.0

    em_count = _count_suffix(tokens, "եմ")
    im_count = _count_suffix(tokens, "իմ")
    em_rate = em_count / token_count if token_count else 0.0
    im_rate = im_count / token_count if token_count else 0.0
    em_vs_im = _safe_log_ratio(em_count + 1.0, im_count + 1.0)

    arm_chars = _armenian_char_count(text)
    char_count = max(len(text), 1)
    arm_ratio = arm_chars / char_count

    punct_count = sum(1 for ch in text if ch in ".!?։,;:")
    punct_rate = punct_count / char_count

    classical_count = text.count("իւ") + text.count("եա")
    classical_rate = classical_count / char_count

    hyastan_proxy_count = text.count("ություն") + text.count("ութիւն")
    hyastan_proxy_rate = hyastan_proxy_count / max(token_count, 1)

    return [
        math.log(token_count + 1.0),
        ttr,
        avg_sentence_len,
        em_rate,
        im_rate,
        em_vs_im,
        arm_ratio,
        punct_rate,
        classical_rate,
        hyastan_proxy_rate,
    ]


def _iter_metadata_entries(corpus_base: Path) -> list[dict]:
    entries: list[dict] = []
    for meta_file in corpus_base.glob("*_metadata.jsonl"):
        with open(meta_file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def build_feature_matrix(corpus_base: Path, max_rows: int = 5000) -> tuple[list[FeatureRow], np.ndarray]:
    """Build feature rows and matrix from corpus metadata + text files."""
    entries = _iter_metadata_entries(corpus_base)
    rows: list[FeatureRow] = []

    for entry in entries:
        if len(rows) >= max_rows:
            break

        text_file = entry.get("text_file")
        if not text_file:
            continue

        source_name = entry.get("source_name", "unknown")
        dialect = entry.get("dialect", "unknown")
        subcategory = entry.get("dialect_subcategory") or "unknown"
        language_code = entry.get("language_code") or "unknown"
        region = entry.get("region") or "unknown"

        # Locate text file by trying common roots.
        candidate_paths = [
            corpus_base / "wikipedia" / "extracted" / text_file,
            corpus_base / "wikipedia_ea" / text_file,
            corpus_base / "news_ea" / "a1plus" / text_file,
            corpus_base / "news_ea" / "aravot" / text_file,
            corpus_base / "news_ea" / "armenpress" / text_file,
            corpus_base / "news_ea" / "armtimes" / text_file,
        ]

        text_path: Optional[Path] = None
        for c in candidate_paths:
            if c.exists():
                text_path = c
                break

        if text_path is None:
            # Fallback recursive find by filename.
            matches = list(corpus_base.rglob(text_file))
            if matches:
                text_path = matches[0]

        if text_path is None or not text_path.exists():
            continue

        try:
            text = text_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        feature_vector = _build_feature_vector(text)
        rows.append(
            FeatureRow(
                text_file=text_file,
                source_name=source_name,
                dialect=dialect,
                dialect_subcategory=subcategory,
                language_code=language_code,
                region=region,
                feature_vector=feature_vector,
            )
        )

    if not rows:
        return rows, np.zeros((0, 0), dtype=float)

    matrix = np.array([r.feature_vector for r in rows], dtype=float)
    return rows, matrix


def run_pca_dbscan(
    matrix: np.ndarray,
    pca_dims: int = 2,
    dbscan_eps: float = 0.8,
    dbscan_min_samples: int = 8,
) -> tuple[np.ndarray, np.ndarray]:
    """Run PCA + DBSCAN.

    Requires scikit-learn. Raises RuntimeError with install guidance if missing.
    """
    try:
        from sklearn.cluster import DBSCAN
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        raise RuntimeError(
            "scikit-learn is required for PCA/DBSCAN. Install with `pip install scikit-learn`."
        ) from exc

    if matrix.size == 0:
        return np.zeros((0, pca_dims), dtype=float), np.zeros((0,), dtype=int)

    scaler = StandardScaler()
    x = scaler.fit_transform(matrix)

    pca = PCA(n_components=pca_dims, random_state=42)
    pca_coords = pca.fit_transform(x)

    dbscan = DBSCAN(eps=dbscan_eps, min_samples=dbscan_min_samples)
    labels = dbscan.fit_predict(x)

    return pca_coords, labels


def write_outputs(rows: list[FeatureRow], pca_coords: np.ndarray, labels: np.ndarray, out_prefix: Path) -> None:
    """Write clustering outputs as JSON and CSV."""
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    json_rows = []
    for i, row in enumerate(rows):
        entry = {
            "text_file": row.text_file,
            "source_name": row.source_name,
            "dialect": row.dialect,
            "dialect_subcategory": row.dialect_subcategory,
            "language_code": row.language_code,
            "region": row.region,
            "cluster_label": int(labels[i]) if len(labels) > i else -1,
            "feature_vector": row.feature_vector,
        }
        if pca_coords.shape[1] >= 2:
            entry["pca_x"] = float(pca_coords[i, 0])
            entry["pca_y"] = float(pca_coords[i, 1])
        if pca_coords.shape[1] >= 3:
            entry["pca_z"] = float(pca_coords[i, 2])
        json_rows.append(entry)

    json_path = out_prefix.with_suffix(".json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(json_rows, fh, ensure_ascii=False, indent=2)

    csv_path = out_prefix.with_suffix(".csv")
    header = [
        "text_file",
        "source_name",
        "dialect",
        "dialect_subcategory",
        "language_code",
        "region",
        "cluster_label",
        "pca_x",
        "pca_y",
        "pca_z",
    ]
    with open(csv_path, "w", encoding="utf-8") as fh:
        fh.write(",".join(header) + "\n")
        for i, row in enumerate(rows):
            pca_x = float(pca_coords[i, 0]) if pca_coords.shape[1] >= 1 else 0.0
            pca_y = float(pca_coords[i, 1]) if pca_coords.shape[1] >= 2 else 0.0
            pca_z = float(pca_coords[i, 2]) if pca_coords.shape[1] >= 3 else 0.0
            values = [
                row.text_file,
                row.source_name,
                row.dialect,
                row.dialect_subcategory,
                row.language_code,
                row.region,
                str(int(labels[i]) if len(labels) > i else -1),
                f"{pca_x:.6f}",
                f"{pca_y:.6f}",
                f"{pca_z:.6f}",
            ]
            # Simple CSV escaping for commas.
            values = [v.replace(",", " ") for v in values]
            fh.write(",".join(values) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run dialect subcategory PCA + DBSCAN clustering")
    parser.add_argument("--corpus-base", default="data/raw", help="Corpus base directory")
    parser.add_argument("--max-rows", type=int, default=5000, help="Max rows to include")
    parser.add_argument("--pca-dims", type=int, default=2, choices=[2, 3], help="PCA dimensions")
    parser.add_argument("--dbscan-eps", type=float, default=0.8, help="DBSCAN eps")
    parser.add_argument("--dbscan-min-samples", type=int, default=8, help="DBSCAN min samples")
    parser.add_argument(
        "--out-prefix",
        default="results/dialect_subcategory_clusters",
        help="Output prefix without extension",
    )
    args = parser.parse_args()

    corpus_base = Path(args.corpus_base)
    rows, matrix = build_feature_matrix(corpus_base=corpus_base, max_rows=args.max_rows)
    if matrix.size == 0:
        raise SystemExit("No feature rows produced. Ensure metadata and text files exist.")

    pca_coords, labels = run_pca_dbscan(
        matrix,
        pca_dims=args.pca_dims,
        dbscan_eps=args.dbscan_eps,
        dbscan_min_samples=args.dbscan_min_samples,
    )

    write_outputs(rows, pca_coords, labels, Path(args.out_prefix))

    n_clusters = len(set(labels.tolist()) - {-1})
    n_noise = int(np.sum(labels == -1))
    print(f"Rows clustered: {len(rows)}")
    print(f"Clusters found: {n_clusters}")
    print(f"Noise points: {n_noise}")
    print(f"Output prefix: {args.out_prefix}")


if __name__ == "__main__":
    main()
