"""Extract pair-aligned WA/EA orthographic load metrics.

This module computes metrics for equivalent Western Armenian (WA) and
Eastern Armenian (EA) forms. It focuses on orthographic expansion signals:

- letter_delta: letter-count difference for equivalent forms
- space_delta: whitespace-count difference for equivalent forms
- orthographic_load: weighted combination of the two

Supported input JSON formats:
1) List of pairs: [["west", "east"], ...]
2) List of objects: [{"western": "...", "eastern": "..."}, ...]
3) Mapping object keyed by Eastern form:
   {
     "eastern_form": {
       "canonical_western_form": "western_form",
       "confidence": 0.92
     }
   }

Usage:
    python -m armenian_corpus_core.linguistics.augmentation.dialect_pair_metrics \
      --pairs cache/variant_pairs_starter.json \
      --out-jsonl data/metrics/dialect_pair_metrics.jsonl \
      --out-summary data/metrics/dialect_load_summary.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, median
from typing import Any
from typing import Sequence


@dataclass
class DialectPairRecord:
    """Single pair-level metric record."""

    pair_id: str
    western_form: str
    eastern_form: str
    western_letter_count: int
    eastern_letter_count: int
    western_space_count: int
    eastern_space_count: int
    letter_delta: int
    space_delta: int
    orthographic_load: float
    confidence: float | None = None
    source: str | None = None


@dataclass
class DialectMetricsSummary:
    """Corpus-level aggregate summary for pair metrics."""

    total_pairs: int
    mean_letter_delta: float
    median_letter_delta: float
    mean_space_delta: float
    median_space_delta: float
    mean_orthographic_load: float
    median_orthographic_load: float
    pct_eastern_more_letters: float
    pct_eastern_more_spaces: float
    pct_equal_letter_count: float
    pct_equal_space_count: float


def _count_letters(text: str) -> int:
    """Count letters/characters excluding literal spaces.

    We treat spaces as a separate signal via ``space_delta``.
    """
    return len(text.replace(" ", ""))


def _count_spaces(text: str) -> int:
    """Count literal spaces in a form."""
    return text.count(" ")


def _compute_record(
    western_form: str,
    eastern_form: str,
    *,
    alpha: float,
    beta: float,
    pair_id: str,
    confidence: float | None = None,
    source: str | None = None,
) -> DialectPairRecord:
    west_letters = _count_letters(western_form)
    east_letters = _count_letters(eastern_form)
    west_spaces = _count_spaces(western_form)
    east_spaces = _count_spaces(eastern_form)

    letter_delta = east_letters - west_letters
    space_delta = east_spaces - west_spaces
    load = alpha * letter_delta + beta * space_delta

    return DialectPairRecord(
        pair_id=pair_id,
        western_form=western_form,
        eastern_form=eastern_form,
        western_letter_count=west_letters,
        eastern_letter_count=east_letters,
        western_space_count=west_spaces,
        eastern_space_count=east_spaces,
        letter_delta=letter_delta,
        space_delta=space_delta,
        orthographic_load=round(load, 6),
        confidence=confidence,
        source=source,
    )


def _parse_pairs_payload(payload: Any) -> list[tuple[str, str, float | None, str | None]]:
    """Normalize supported input payloads into a common tuple format."""
    normalized: list[tuple[str, str, float | None, str | None]] = []

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                west = str(item[0]).strip()
                east = str(item[1]).strip()
                if west and east:
                    normalized.append((west, east, None, None))
                continue

            if isinstance(item, dict):
                west = str(item.get("western") or item.get("west") or "").strip()
                east = str(item.get("eastern") or item.get("east") or "").strip()
                if not west or not east:
                    continue
                conf_raw = item.get("confidence")
                confidence = float(conf_raw) if isinstance(conf_raw, (float, int)) else None
                source = str(item.get("source")).strip() if item.get("source") else None
                normalized.append((west, east, confidence, source))

    elif isinstance(payload, dict):
        # Expected mapping format keyed by Eastern form.
        for east, meta in payload.items():
            if not isinstance(meta, dict):
                continue
            west = str(meta.get("canonical_western_form") or "").strip()
            east_form = str(east).strip()
            if not west or not east_form:
                continue
            conf_raw = meta.get("confidence")
            confidence = float(conf_raw) if isinstance(conf_raw, (float, int)) else None
            source = "west_east_usage_mapping"
            normalized.append((west, east_form, confidence, source))

    return normalized


def load_pairs(path: str | Path) -> list[tuple[str, str, float | None, str | None]]:
    """Load and normalize WA/EA equivalent pairs from JSON."""
    in_path = Path(path)
    if not in_path.exists():
        raise FileNotFoundError(f"Pairs file not found: {in_path}")

    # Use utf-8-sig so JSON files saved by some Windows tools with BOM still parse.
    payload = json.loads(in_path.read_text(encoding="utf-8-sig"))
    pairs = _parse_pairs_payload(payload)
    if not pairs:
        raise ValueError("No valid WA/EA pairs found in input JSON.")

    return pairs


def compute_dialect_pair_metrics(
    pairs: Sequence[tuple[str, str, float | None, str | None]],
    *,
    alpha: float = 1.0,
    beta: float = 2.0,
) -> list[DialectPairRecord]:
    """Compute pair-level dialect metrics for normalized pair tuples."""
    records: list[DialectPairRecord] = []
    for idx, (west, east, confidence, source) in enumerate(pairs, start=1):
        records.append(
            _compute_record(
                west,
                east,
                alpha=alpha,
                beta=beta,
                pair_id=f"pair_{idx:06d}",
                confidence=confidence,
                source=source,
            )
        )
    return records


def summarize_records(records: list[DialectPairRecord]) -> DialectMetricsSummary:
    """Build aggregate summary statistics for computed records."""
    if not records:
        raise ValueError("Cannot summarize empty record list.")

    letter_deltas = [r.letter_delta for r in records]
    space_deltas = [r.space_delta for r in records]
    loads = [r.orthographic_load for r in records]
    total = len(records)

    def pct(count: int) -> float:
        return round((count / total) * 100.0, 4)

    return DialectMetricsSummary(
        total_pairs=total,
        mean_letter_delta=round(mean(letter_deltas), 6),
        median_letter_delta=round(float(median(letter_deltas)), 6),
        mean_space_delta=round(mean(space_deltas), 6),
        median_space_delta=round(float(median(space_deltas)), 6),
        mean_orthographic_load=round(mean(loads), 6),
        median_orthographic_load=round(float(median(loads)), 6),
        pct_eastern_more_letters=pct(sum(1 for d in letter_deltas if d > 0)),
        pct_eastern_more_spaces=pct(sum(1 for d in space_deltas if d > 0)),
        pct_equal_letter_count=pct(sum(1 for d in letter_deltas if d == 0)),
        pct_equal_space_count=pct(sum(1 for d in space_deltas if d == 0)),
    )


def save_records_jsonl(records: list[DialectPairRecord], path: str | Path) -> Path:
    """Save pair-level records as JSONL."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [json.dumps(asdict(record), ensure_ascii=False) for record in records]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def save_summary_json(summary: DialectMetricsSummary, path: str | Path) -> Path:
    """Save summary object as JSON."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(asdict(summary), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out


def _save_optional_parquet(records: list[DialectPairRecord], path: str | Path) -> Path | None:
    """Save records to parquet if pandas is available; otherwise skip."""
    try:
        import pandas as pd  # type: ignore
    except Exception:
        return None

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([asdict(record) for record in records])
    frame.to_parquet(out, index=False)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m armenian_corpus_core.linguistics.augmentation.dialect_pair_metrics",
        description="Compute WA/EA letter/space orthographic load metrics from aligned pairs.",
    )
    parser.add_argument("--pairs", default="cache/variant_pairs_starter.json")
    parser.add_argument("--out-jsonl", default="data/metrics/dialect_pair_metrics.jsonl")
    parser.add_argument("--out-summary", default="data/metrics/dialect_load_summary.json")
    parser.add_argument("--out-parquet", default="")
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--beta", type=float, default=2.0)
    args = parser.parse_args()

    pairs = load_pairs(args.pairs)
    records = compute_dialect_pair_metrics(pairs, alpha=args.alpha, beta=args.beta)
    summary = summarize_records(records)

    jsonl_path = save_records_jsonl(records, args.out_jsonl)
    summary_path = save_summary_json(summary, args.out_summary)

    parquet_path = None
    if args.out_parquet:
        parquet_path = _save_optional_parquet(records, args.out_parquet)

    print(f"Loaded {len(pairs)} pair(s) from: {args.pairs}")
    print(f"Saved pair metrics JSONL: {jsonl_path}")
    print(f"Saved summary JSON: {summary_path}")
    if args.out_parquet:
        if parquet_path is not None:
            print(f"Saved parquet: {parquet_path}")
        else:
            print("Skipped parquet output (pandas not available).")


if __name__ == "__main__":
    main()
