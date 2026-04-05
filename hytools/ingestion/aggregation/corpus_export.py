"""Export corpus documents from MongoDB to Parquet, Hugging Face, and release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

from hytools.config.settings import load_config

logger = logging.getLogger(__name__)

_EXPORT_FIELDS = [
    "_id",
    "content_hash",
    "normalized_content_hash",
    "source",
    "title",
    "text",
    "url",
    "author",
    "metadata.source_name",
    "metadata.source_url",
    "metadata.domain",
    "metadata.source_language_code",
    "metadata.internal_language_code",
    "metadata.internal_language_branch",
    "metadata.wa_score",
    "metadata.publication_date",
    "metadata.original_date",
    "metadata.source_type",
    "metadata.content_type",
    "metadata.writing_category",
    "metadata.dialect",
    "metadata.dialect_label",
    "metadata.word_count",
    "metadata.char_count",
]
_DEFAULT_RELEASE_SEED = "hytools-release-v1"


def _require_pandas():
    try:
        pd = importlib.import_module("pandas")
    except ImportError as exc:  # pragma: no cover - handled by caller
        raise ImportError(
            "pandas and pyarrow are required for Parquet export. Install via: pip install hytools[export]"
        ) from exc
    return pd


def _require_datasets():
    try:
        Dataset = importlib.import_module("datasets").Dataset
    except ImportError as exc:  # pragma: no cover - handled by caller
        raise ImportError(
            "datasets is required for Hugging Face export. Install via: pip install hytools[huggingface]"
        ) from exc
    return Dataset


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _release_row_key(row: dict[str, Any]) -> str:
    return str(row.get("content_hash") or row.get("normalized_content_hash") or row.get("id") or "")


def _release_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (_release_row_key(row), str(row.get("id") or ""))


def _flatten_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested document fields into a stable tabular export row."""
    meta = doc.get("metadata") or {}
    flat: dict[str, Any] = {}
    flat["id"] = str(doc.get("_id", ""))
    flat["content_hash"] = doc.get("content_hash") or meta.get("content_hash") or flat["id"]
    flat["normalized_content_hash"] = doc.get("normalized_content_hash") or meta.get("normalized_content_hash") or ""
    flat["text"] = doc.get("text", "")
    flat["source"] = doc.get("source") or meta.get("source") or meta.get("source_name") or ""
    flat["source_name"] = meta.get("source_name") or ""
    flat["source_url"] = doc.get("url") or meta.get("source_url") or meta.get("url") or ""
    flat["domain"] = meta.get("domain") or ""
    flat["author"] = doc.get("author") or meta.get("author") or ""
    flat["title"] = doc.get("title") or meta.get("title") or ""
    flat["wa_score"] = meta.get("wa_score")
    flat["source_language_code"] = meta.get("source_language_code") or ""
    flat["internal_language_code"] = meta.get("internal_language_code") or ""
    flat["internal_language_branch"] = meta.get("internal_language_branch") or ""
    flat["publication_date"] = meta.get("publication_date") or ""
    flat["original_date"] = meta.get("original_date") or ""
    flat["source_type"] = meta.get("source_type") or ""
    flat["content_type"] = meta.get("content_type") or ""
    flat["writing_category"] = meta.get("writing_category") or ""
    flat["dialect"] = meta.get("dialect") or ""
    flat["dialect_label"] = meta.get("dialect_label") or ""
    flat["word_count"] = meta.get("word_count")
    flat["char_count"] = meta.get("char_count")
    return flat


def _iter_documents(config: dict, dialect_filter: str | None = None) -> Iterator[dict[str, Any]]:
    """Yield flattened documents from MongoDB."""
    from hytools.ingestion._shared.helpers import open_mongodb_client

    query: dict[str, Any] = {"text": {"$exists": True, "$ne": ""}}
    if dialect_filter:
        query["metadata.internal_language_branch"] = dialect_filter

    with open_mongodb_client(config) as client:
        if client is None:
            logger.error("MongoDB unavailable — cannot export")
            return
        coll = client.db["documents"]
        projection = {field: 1 for field in _EXPORT_FIELDS}
        projection["_id"] = 1
        for doc in coll.find(query, projection):
            yield _flatten_doc(doc)


def _write_parquet_rows(rows: Sequence[dict[str, Any]], output_path: Path) -> None:
    pd = _require_pandas()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(list(rows)).to_parquet(output_path, index=False, engine="pyarrow")


def _write_huggingface_rows(rows: Sequence[dict[str, Any]], output_path: Path) -> None:
    Dataset = _require_datasets()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Dataset.from_list(list(rows)).save_to_disk(str(output_path))


def _artifact_sha256(path: Path) -> str:
    if path.is_dir():
        digest = hashlib.sha256()
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            digest.update(child.relative_to(path).as_posix().encode("utf-8"))
            with child.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        return digest.hexdigest()

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_parquet(
    config: dict,
    output_path: str | Path = "data/export/corpus.parquet",
    dialect_filter: str | None = None,
) -> dict[str, Any]:
    """Export corpus to a Parquet file."""
    output = Path(output_path)
    rows = sorted(list(_iter_documents(config, dialect_filter)), key=_release_sort_key)
    if not rows:
        logger.warning("No documents to export")
        return {"rows": 0, "output": str(output), "format": "parquet"}

    _write_parquet_rows(rows, output)
    logger.info("Exported %d documents to %s", len(rows), output)
    return {"rows": len(rows), "output": str(output), "format": "parquet"}


def export_huggingface(
    config: dict,
    output_path: str | Path = "data/export/corpus_hf",
    dialect_filter: str | None = None,
) -> dict[str, Any]:
    """Export corpus as a Hugging Face dataset directory."""
    output = Path(output_path)
    rows = sorted(list(_iter_documents(config, dialect_filter)), key=_release_sort_key)
    if not rows:
        logger.warning("No documents to export")
        return {"rows": 0, "output": str(output), "format": "huggingface"}

    _write_huggingface_rows(rows, output)
    logger.info("Exported %d documents to %s (HF Dataset)", len(rows), output)
    return {"rows": len(rows), "output": str(output), "format": "huggingface"}


def _stable_bucket_for_row(
    row: dict[str, Any],
    *,
    split_seed: str,
    train_ratio: float,
    validation_ratio: float,
) -> str:
    digest = hashlib.sha256(f"{split_seed}:{_release_row_key(row)}".encode("utf-8")).hexdigest()
    position = int(digest[:16], 16) / float(16**16)
    if position < train_ratio:
        return "train"
    if position < train_ratio + validation_ratio:
        return "validation"
    return "test"


def partition_release_rows(
    rows: Sequence[dict[str, Any]],
    *,
    split_seed: str,
    train_ratio: float,
    validation_ratio: float,
    test_ratio: float,
) -> dict[str, list[dict[str, Any]]]:
    total = train_ratio + validation_ratio + test_ratio
    if abs(total - 1.0) > 1e-6:
        raise ValueError("train_ratio + validation_ratio + test_ratio must sum to 1.0")

    partitions: dict[str, list[dict[str, Any]]] = {"train": [], "validation": [], "test": []}
    for row in sorted(rows, key=_release_sort_key):
        bucket = _stable_bucket_for_row(
            row,
            split_seed=split_seed,
            train_ratio=train_ratio,
            validation_ratio=validation_ratio,
        )
        partition_row = dict(row)
        partition_row["split"] = bucket
        partitions[bucket].append(partition_row)
    return partitions


def _release_artifact_record(root: Path, path: Path, *, row_count: int, artifact_type: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "rows": row_count,
        "type": artifact_type,
        "sha256": _artifact_sha256(path),
    }


def _build_dataset_card(manifest: dict[str, Any]) -> str:
    split_counts = manifest.get("split_counts", {})
    source_counts = manifest.get("source_counts", {})
    lines = [
        f"# {manifest['dataset_name']}",
        "",
        f"Version: {manifest['dataset_version']}",
        f"Generated: {manifest['generated_at']}",
        f"Dialect filter: {manifest.get('dialect_filter') or 'none'}",
        f"Deterministic split seed: {manifest['split_seed']}",
        "",
        "## Split counts",
        "",
    ]
    for split_name in ("train", "validation", "test"):
        lines.append(f"- {split_name}: {split_counts.get(split_name, 0)}")

    lines.extend(["", "## Sources", ""])
    for source, count in sorted(source_counts.items()):
        lines.append(f"- {source}: {count}")

    lines.extend(["", "## Artifacts", ""])
    for artifact in manifest.get("artifacts", []):
        lines.append(
            f"- {artifact['path']} ({artifact['type']}, rows={artifact['rows']}, sha256={artifact['sha256']})"
        )

    return "\n".join(lines) + "\n"


def _write_checksums(root: Path, artifacts: Sequence[dict[str, Any]], output_path: Path) -> None:
    lines = [f"{artifact['sha256']}  {artifact['path']}" for artifact in artifacts]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_release(
    config: dict,
    *,
    output_path: str | Path | None = None,
    dialect_filter: str | None = None,
    split_seed: str | None = None,
    dataset_name: str | None = None,
    dataset_version: str | None = None,
    include_huggingface: bool | None = None,
) -> dict[str, Any]:
    """Build a deterministic release with split artifacts, manifest, checksums, and a dataset card."""
    export_cfg = config.get("export") or {}
    release_cfg = export_cfg.get("release") or {}

    root = Path(output_path or release_cfg.get("output_dir") or "data/releases/latest")
    root.mkdir(parents=True, exist_ok=True)

    selected_dialect = dialect_filter if dialect_filter is not None else export_cfg.get("dialect_filter")
    selected_seed = split_seed or release_cfg.get("split_seed") or _DEFAULT_RELEASE_SEED
    selected_name = dataset_name or release_cfg.get("dataset_name") or "hytools-western-armenian-corpus"
    selected_version = dataset_version or release_cfg.get("dataset_version") or "0.1.0"
    selected_include_hf = release_cfg.get("include_huggingface", True) if include_huggingface is None else include_huggingface
    include_full_parquet = bool(release_cfg.get("include_full_parquet", True))
    include_dataset_card = bool(release_cfg.get("include_dataset_card", True))
    include_checksums = bool(release_cfg.get("include_checksums", True))
    train_ratio = float(release_cfg.get("train_ratio", 0.90))
    validation_ratio = float(release_cfg.get("validation_ratio", 0.05))
    test_ratio = float(release_cfg.get("test_ratio", 0.05))

    rows = sorted(list(_iter_documents(config, selected_dialect)), key=_release_sort_key)
    if not rows:
        logger.warning("No documents available for release generation")
        return {
            "rows": 0,
            "output": str(root),
            "split_counts": {"train": 0, "validation": 0, "test": 0},
            "artifacts": [],
        }

    partitions = partition_release_rows(
        rows,
        split_seed=selected_seed,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        test_ratio=test_ratio,
    )

    artifacts: list[dict[str, Any]] = []
    splits_dir = root / "splits"
    splits_dir.mkdir(parents=True, exist_ok=True)
    for split_name, split_rows in partitions.items():
        split_path = splits_dir / f"{split_name}.parquet"
        _write_parquet_rows(split_rows, split_path)
        artifacts.append(_release_artifact_record(root, split_path, row_count=len(split_rows), artifact_type="parquet-split"))

    if include_full_parquet:
        full_path = root / "corpus.parquet"
        _write_parquet_rows(rows, full_path)
        artifacts.append(_release_artifact_record(root, full_path, row_count=len(rows), artifact_type="parquet-full"))

    if selected_include_hf:
        hf_root = root / "huggingface"
        for split_name, split_rows in partitions.items():
            hf_path = hf_root / split_name
            _write_huggingface_rows(split_rows, hf_path)
            artifacts.append(_release_artifact_record(root, hf_path, row_count=len(split_rows), artifact_type="huggingface-split"))

    manifest = {
        "dataset_name": selected_name,
        "dataset_version": selected_version,
        "generated_at": _utcnow_iso(),
        "dialect_filter": selected_dialect,
        "split_seed": selected_seed,
        "split_counts": {key: len(value) for key, value in partitions.items()},
        "source_counts": dict(sorted(Counter((row.get("source") or "unknown") for row in rows).items())),
        "artifacts": artifacts,
    }

    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts.append(_release_artifact_record(root, manifest_path, row_count=len(rows), artifact_type="manifest"))

    if include_dataset_card:
        card_path = root / "README.md"
        card_path.write_text(_build_dataset_card(manifest), encoding="utf-8")
        artifacts.append(_release_artifact_record(root, card_path, row_count=len(rows), artifact_type="dataset-card"))

    if include_checksums:
        checksum_path = root / "SHA256SUMS.txt"
        _write_checksums(root, artifacts, checksum_path)
        artifacts.append(_release_artifact_record(root, checksum_path, row_count=len(rows), artifact_type="checksums"))

    logger.info("Built release with %d documents at %s", len(rows), root)
    return {
        "rows": len(rows),
        "output": str(root),
        "split_counts": manifest["split_counts"],
        "dataset_name": selected_name,
        "dataset_version": selected_version,
        "split_seed": selected_seed,
        "artifacts": artifacts,
    }


def run(config: dict) -> dict[str, Any]:
    """Ingestion runner entry point for non-release exports."""
    results: dict[str, Any] = {}
    export_cfg = config.get("export") or {}
    export_dir = Path(export_cfg.get("output_dir", "data/export"))
    dialect = export_cfg.get("dialect_filter")
    formats = [str(item).lower() for item in (export_cfg.get("formats") or ["parquet", "huggingface"])]

    if "parquet" in formats:
        try:
            results["parquet"] = export_parquet(config, output_path=export_dir / "corpus.parquet", dialect_filter=dialect)
        except ImportError as exc:
            logger.warning("Parquet export skipped: %s", exc)
            results["parquet"] = {"skipped": True, "reason": str(exc)}

    if "huggingface" in formats:
        try:
            results["huggingface"] = export_huggingface(config, output_path=export_dir / "corpus_hf", dialect_filter=dialect)
        except ImportError as exc:
            logger.warning("HuggingFace export skipped: %s", exc)
            results["huggingface"] = {"skipped": True, "reason": str(exc)}

    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export corpus to Parquet, Hugging Face, or deterministic release artifacts")
    parser.add_argument("--format", choices=["parquet", "huggingface", "release", "all"], default="all")
    parser.add_argument("--output", default=None, help="Output directory or file path")
    parser.add_argument("--dialect", default=None, help="Filter by internal_language_branch (e.g. hye-w)")
    parser.add_argument("--config", default="config/settings.yaml")
    parser.add_argument("--seed", default=None, help="Override deterministic release seed")
    parser.add_argument("--dataset-name", default=None, help="Override release dataset name")
    parser.add_argument("--dataset-version", default=None, help="Override release dataset version")
    parser.add_argument("--no-huggingface", action="store_true", help="Skip Hugging Face release artifacts")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        cfg = load_config(args.config)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output = Path(args.output) if args.output else None

    if args.format in ("parquet", "all"):
        try:
            target = output if output is not None and args.format == "parquet" else Path((cfg.get("export") or {}).get("output_dir", "data/export")) / "corpus.parquet"
            print(json.dumps(export_parquet(cfg, target, args.dialect), ensure_ascii=False, indent=2))
        except ImportError as exc:
            print(f"Parquet export unavailable: {exc}", file=sys.stderr)
            if args.format == "parquet":
                return 1

    if args.format in ("huggingface", "all"):
        try:
            target = output if output is not None and args.format == "huggingface" else Path((cfg.get("export") or {}).get("output_dir", "data/export")) / "corpus_hf"
            print(json.dumps(export_huggingface(cfg, target, args.dialect), ensure_ascii=False, indent=2))
        except ImportError as exc:
            print(f"HuggingFace export unavailable: {exc}", file=sys.stderr)
            if args.format == "huggingface":
                return 1

    if args.format == "release":
        try:
            result = build_release(
                cfg,
                output_path=output,
                dialect_filter=args.dialect,
                split_seed=args.seed,
                dataset_name=args.dataset_name,
                dataset_version=args.dataset_version,
                include_huggingface=False if args.no_huggingface else None,
            )
        except ImportError as exc:
            print(f"Release export unavailable: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    raise SystemExit(main())
