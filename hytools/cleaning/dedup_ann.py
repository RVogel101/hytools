"""ANN-based near-duplicate detection for hytools corpus cleaning."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, List, Literal, Optional, Sequence, Tuple

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    import faiss  # type: ignore[reportMissingModuleSource]
except ImportError:  # pragma: no cover
    faiss = None

try:
    from annoy import AnnoyIndex  # type: ignore[reportMissingModuleSource]
except ImportError:  # pragma: no cover
    AnnoyIndex = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:  # pragma: no cover
    TfidfVectorizer = None

logger = logging.getLogger(__name__)


def _to_numpy(vectors: Sequence[Sequence[float]]) -> "np.ndarray":
    if np is None:
        raise RuntimeError("numpy is required for dedup_ann operations")
    arr = np.array(vectors, dtype=np.float32)
    if arr.ndim != 2:
        raise ValueError("vectors must be 2D")
    return arr


def _dedup_bruteforce(vectors: "np.ndarray", distance_threshold: float) -> List[int]:
    kept: List[int] = []
    for i, vec in enumerate(vectors):
        is_dup = False
        for j in kept:
            d = float(np.linalg.norm(vec - vectors[j]))
            if d <= distance_threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(i)
    return kept


def deduplicate_vectors(
    vectors: Sequence[Sequence[float]],
    distance_threshold: float = 1.0,
    backend: Literal["annoy", "faiss", "brute"] = "annoy",
    metric: Literal["euclidean", "angular"] = "euclidean",
    n_trees: int = 10,
    n_neighbors: int = 32,
    random_seed: int = 42,
) -> List[int]:
    """Return a list of kept indices after ANN dedupe.

    This is deterministic when using fixed input order and fixed random_seed.
    """
    if len(vectors) == 0:
        return []

    data = _to_numpy(vectors)
    n, d = data.shape

    if backend == "annoy" and AnnoyIndex is not None:
        if metric == "euclidean":
            annoy_metric = "euclidean"
        elif metric == "angular":
            annoy_metric = "angular"
        else:
            raise ValueError("metric must be euclidean or angular")

        index = AnnoyIndex(d, annoy_metric)
        for i in range(n):
            index.add_item(i, data[i].tolist())
        index.build(n_trees, n_jobs=-1)

        kept: List[int] = []
        for i in range(n):
            idx_list, distances = index.get_nns_by_item(i, n_neighbors, include_distances=True)
            for j, dist in zip(idx_list, distances):
                if j == i:
                    continue
                if j in kept and dist <= distance_threshold:
                    logger.debug("Vector %d is near-duplicate to %d (dist=%.4f)", i, j, dist)
                    break
            else:
                kept.append(i)
        return kept

    if backend == "faiss" and faiss is not None:
        if metric == "euclidean":
            index = faiss.IndexFlatL2(d)
            data_index = data
            if data_index.dtype != np.float32:
                data_index = data.astype(np.float32)
        elif metric == "angular":
            index = faiss.IndexFlatIP(d)
            data_index = data.copy()
            faiss.normalize_L2(data_index)
        else:
            raise ValueError("metric must be euclidean or angular")

        index.add(data_index)
        _, neighbors = index.search(data_index, n_neighbors)

        kept = []
        for i in range(n):
            for j in neighbors[i]:
                if j == i:
                    continue
                if j in kept:
                    if metric == "euclidean":
                        dist = np.linalg.norm(data[i] - data[j])
                    else:
                        dist = float(1 - np.dot(data[i], data[j]) / (np.linalg.norm(data[i]) * np.linalg.norm(data[j]) + 1e-12))
                    if dist <= distance_threshold:
                        logger.debug("Vector %d is near-duplicate to %d (dist=%.4f)", i, j, dist)
                        break
            else:
                kept.append(i)
        return kept

    logger.warning("Using brute-force ANN duplicate elimination; install annoy or faiss for faster performance")
    return _dedup_bruteforce(data, distance_threshold)


def _read_texts_and_paths(input_dir: Path) -> Tuple[List[Path], List[str]]:
    paths = sorted(input_dir.rglob("*.txt"))
    texts = [p.read_text(encoding="utf-8", errors="replace") for p in paths]
    return paths, texts


def _build_vectors(texts: List[str]) -> "np.ndarray":
    if TfidfVectorizer is not None:
        vec = TfidfVectorizer(strip_accents="unicode", max_features=8192)
        matrix = vec.fit_transform(texts).toarray().astype(np.float32)
        return matrix

    if np is None:
        raise RuntimeError("Either sklearn or numpy is required for vectorization")

    # fallback: simple char-histogram vector
    feats = []
    alpha = [chr(i) for i in range(32, 127)]
    for t in texts:
        counts = [float(t.count(c)) for c in alpha]
        feats.append(counts)
    return np.array(feats, dtype=np.float32)


def save_precomputed_vectors(path: Path, file_paths: List[Path], vectors: "np.ndarray") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, paths=[str(p) for p in file_paths], vectors=vectors)


def load_precomputed_vectors(path: Path) -> Tuple[List[Path], "np.ndarray"]:
    data = np.load(path, allow_pickle=True)
    paths = [Path(p) for p in data["paths"].tolist()]
    vectors = data["vectors"].astype(np.float32)
    return paths, vectors


def _save_ann_index(index_path: Path, vectors: "np.ndarray", backend: str, metric: str, n_trees: int) -> None:
    index_path.parent.mkdir(parents=True, exist_ok=True)

    if backend == "annoy" and AnnoyIndex is not None:
        _, d = vectors.shape
        annoy_index = AnnoyIndex(d, metric)
        for i in range(len(vectors)):
            annoy_index.add_item(i, vectors[i].tolist())
        annoy_index.build(n_trees)
        annoy_index.save(str(index_path))
        return

    if backend == "faiss" and faiss is not None:
        n, d = vectors.shape
        data_index = vectors.astype(np.float32)
        if metric == "angular":
            faiss.normalize_L2(data_index)
            index = faiss.IndexFlatIP(d)
        else:
            index = faiss.IndexFlatL2(d)
        index.add(data_index)
        faiss.write_index(index, str(index_path))
        return

    raise RuntimeError("ANN index persistence requires annoy or faiss")


def deduplicate_directory(
    input_dir: Path,
    output_dir: Path,
    distance_threshold: float = 1.0,
    backend: Literal["annoy", "faiss", "brute"] = "annoy",
    metric: Literal["euclidean", "angular"] = "euclidean",
    n_trees: int = 10,
    n_neighbors: int = 32,
    vectors_path: Optional[Path] = None,
    index_path: Optional[Path] = None,
    force_rebuild: bool = False,
) -> Tuple[int, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_paths, texts = _read_texts_and_paths(input_dir)
    total = len(file_paths)

    if vectors_path is not None and vectors_path.exists() and not force_rebuild:
        loaded_paths, vectors = load_precomputed_vectors(vectors_path)
        if len(loaded_paths) != total or set(loaded_paths) != set(file_paths):
            logger.info("Vector cache mismatch or incomplete; rebuilding vectors")
            vectors = _build_vectors(texts)
            save_precomputed_vectors(vectors_path, file_paths, vectors)
        else:
            vectors = vectors
    else:
        vectors = _build_vectors(texts)
        if vectors_path is not None:
            save_precomputed_vectors(vectors_path, file_paths, vectors)

    kept_indices = deduplicate_vectors(
        vectors.tolist(),
        distance_threshold=distance_threshold,
        backend=backend,
        metric=metric,
        n_trees=n_trees,
        n_neighbors=n_neighbors,
    )

    kept_set = set(kept_indices)
    kept_count = 0
    for idx, txt_path in enumerate(file_paths):
        if idx in kept_set:
            rel = txt_path.relative_to(input_dir)
            out_path = output_dir / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(txt_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
            kept_count += 1

    if index_path is not None and backend in {"annoy", "faiss"}:
        try:
            _save_ann_index(index_path, _to_numpy(vectors), backend, metric, n_trees)
        except Exception as exc:
            logger.warning("Failed to save ANN index: %s", exc)

    return total, kept_count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(deduplicate_vectors([[0.0], [0.0], [100.0], [100.5]], distance_threshold=0.75, backend="brute"))

