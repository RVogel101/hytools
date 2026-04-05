#!/usr/bin/env python
"""Top-level pipeline orchestrator for cross-stage workflows.

Usage::

    python scripts/run_pipeline.py --stage scrape
    python scripts/run_pipeline.py --stage scrape --only-runner-stage archive_org loc
    python scripts/run_pipeline.py --stage ocr --pdf path/to/file.pdf
    python scripts/run_pipeline.py --stage all --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Sequence

logger = logging.getLogger(__name__)


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    import yaml

    with config_path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _resolve_runner_stage_selection(
    cfg: dict,
    top_level_stage: str,
    only_runner_stages: list[str] | None = None,
    skip_runner_stages: list[str] | None = None,
    *,
    allow_empty: bool = False,
) -> list[str]:
    from hytools.ingestion.runner import _stage_groups

    group_map = _stage_groups(cfg)
    if top_level_stage == "scrape":
        selected = list(group_map.get("scraping", []))
    elif top_level_stage == "ingest":
        selected = list(group_map.get("extraction", [])) + list(group_map.get("postprocessing", []))
    else:
        raise ValueError(f"Unsupported runner-backed stage: {top_level_stage}")

    if only_runner_stages:
        only_set = set(only_runner_stages)
        selected = [name for name in selected if name in only_set]
    if skip_runner_stages:
        skip_set = set(skip_runner_stages)
        selected = [name for name in selected if name not in skip_set]

    if not selected and not allow_empty:
        raise ValueError(
            f"No runner stages remain for top-level stage '{top_level_stage}'. "
            "Adjust --only-runner-stage / --skip-runner-stage."
        )
    return selected


def _run_ocr(cfg: dict, pdf_path: Path | None, overwrite: bool) -> None:
    """Execute the OCR stage."""
    from hytools.ocr.pipeline import run as ocr_run

    ocr_run(config=cfg, pdf_path=pdf_path, overwrite=overwrite)


def _run_clean(cfg: dict, args: argparse.Namespace) -> dict:
    """Execute the cleaning stage. Returns the summary dict."""
    from hytools.cleaning.pipeline import create_clean_corpus

    return create_clean_corpus(
        config=cfg,
        source_collection=args.source_collection,
        output_collection=args.output_collection,
        output_path=args.output,
    )


def _run_scrape(
    cfg: dict,
    only_runner_stages: list[str] | None = None,
    skip_runner_stages: list[str] | None = None,
) -> dict:
    """Execute scraping/acquisition stages via the canonical ingestion runner."""
    from hytools.ingestion.runner import run_pipeline

    selection = _resolve_runner_stage_selection(
        cfg,
        "scrape",
        only_runner_stages=only_runner_stages,
        skip_runner_stages=skip_runner_stages,
    )
    return run_pipeline(cfg, only=selection)


def _run_ingest(
    cfg: dict,
    only_runner_stages: list[str] | None = None,
    skip_runner_stages: list[str] | None = None,
) -> dict:
    """Execute extraction + post-processing stages via the canonical ingestion runner."""
    from hytools.ingestion.runner import run_pipeline

    selection = _resolve_runner_stage_selection(
        cfg,
        "ingest",
        only_runner_stages=only_runner_stages,
        skip_runner_stages=skip_runner_stages,
    )
    return run_pipeline(cfg, only=selection)


def _validate_args(args: argparse.Namespace) -> None:
    if args.pdf is not None and args.stage not in {"ocr", "all"}:
        raise ValueError("--pdf is only valid with --stage ocr or --stage all.")
    if args.stage in {"ocr", "clean"} and (args.only_runner_stage or args.skip_runner_stage):
        raise ValueError(
            "--only-runner-stage and --skip-runner-stage only apply to scrape, ingest, or all."
        )


def _build_execution_plan(args: argparse.Namespace, cfg: dict) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []

    if args.stage in {"scrape", "all"}:
        selection = _resolve_runner_stage_selection(
            cfg,
            "scrape",
            only_runner_stages=args.only_runner_stage,
            skip_runner_stages=args.skip_runner_stage,
            allow_empty=args.stage == "all",
        )
        if selection:
            plan.append(
                {
                    "name": "scrape",
                    "kind": "runner",
                    "runner_stages": selection,
                }
            )

    if args.stage in {"ocr", "all"}:
        plan.append(
            {
                "name": "ocr",
                "kind": "ocr",
                "pdf": str(args.pdf) if args.pdf is not None else None,
                "overwrite": bool(args.overwrite),
            }
        )

    if args.stage in {"clean", "all"}:
        plan.append(
            {
                "name": "clean",
                "kind": "clean",
                "output": args.output,
                "source_collection": args.source_collection,
                "output_collection": args.output_collection,
            }
        )

    if args.stage in {"ingest", "all"}:
        selection = _resolve_runner_stage_selection(
            cfg,
            "ingest",
            only_runner_stages=args.only_runner_stage,
            skip_runner_stages=args.skip_runner_stage,
            allow_empty=args.stage == "all",
        )
        if selection:
            plan.append(
                {
                    "name": "ingest",
                    "kind": "runner",
                    "runner_stages": selection,
                }
            )

    if not plan:
        raise ValueError("No pipeline steps remain after applying the selected filters.")
    return plan


def _log_runner_summary(label: str, summary: dict) -> None:
    ok = sum(1 for stage in summary.get("stages", []) if stage.get("status") == "ok")
    failed = sum(1 for stage in summary.get("stages", []) if stage.get("status") == "failed")
    logger.info("=== %s complete: %d ok, %d failed ===", label, ok, failed)


def _execute_step(cfg: dict, args: argparse.Namespace, step: dict[str, Any]) -> None:
    name = step["name"]
    if name == "scrape":
        logger.info("=== Scraping stage ===")
        summary = _run_scrape(
            cfg,
            only_runner_stages=args.only_runner_stage,
            skip_runner_stages=args.skip_runner_stage,
        )
        _log_runner_summary("Scraping stage", summary)
        return

    if name == "ocr":
        logger.info("=== OCR stage ===")
        _run_ocr(cfg, pdf_path=args.pdf, overwrite=args.overwrite)
        logger.info("=== OCR stage complete ===")
        return

    if name == "clean":
        logger.info("=== Cleaning stage ===")
        summary = _run_clean(cfg, args)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        logger.info("=== Cleaning stage complete ===")
        return

    if name == "ingest":
        logger.info("=== Ingestion stage ===")
        summary = _run_ingest(
            cfg,
            only_runner_stages=args.only_runner_stage,
            skip_runner_stages=args.skip_runner_stage,
        )
        _log_runner_summary("Ingestion stage", summary)
        return

    raise ValueError(f"Unknown execution step: {name}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run hytools cross-stage pipeline steps: scrape, ocr, clean, ingest, or all.",
    )
    parser.add_argument(
        "--stage",
        choices=["scrape", "ocr", "clean", "ingest", "all"],
        default="all",
        help="Which top-level pipeline stage to run (default: all)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/settings.yaml"),
        help="Path to settings.yaml",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved execution plan without running any stages",
    )
    parser.add_argument(
        "--only-runner-stage",
        nargs="*",
        default=[],
        help="Restrict runner-backed steps to these ingestion.runner stage names",
    )
    parser.add_argument(
        "--skip-runner-stage",
        nargs="*",
        default=[],
        help="Skip these ingestion.runner stage names inside scrape/ingest steps",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="Process a single PDF (OCR stage only)",
    )
    parser.add_argument(
        "--overwrite",
        "-f",
        action="store_true",
        help="Re-run OCR on pages even if output already exists",
    )
    parser.add_argument(
        "--output",
        default="data/cleaned_corpus",
        help="Output path for cleaned corpus",
    )
    parser.add_argument(
        "--source-collection",
        default="documents",
        help="MongoDB source collection for cleaning",
    )
    parser.add_argument(
        "--output-collection",
        default="documents_cleaned",
        help="MongoDB staging collection for cleaning",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        _validate_args(args)
        cfg = _load_config(args.config)
        plan = _build_execution_plan(args, cfg)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.dry_run:
        print(
            json.dumps(
                {
                    "stage": args.stage,
                    "config": str(args.config),
                    "steps": plan,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    logger.info("Running pipeline stage: %s", args.stage)
    current_step: dict[str, Any] | None = None
    try:
        for current_step in plan:
            _execute_step(cfg, args, current_step)
    except KeyboardInterrupt:
        step_name = current_step["name"] if current_step is not None else args.stage
        logger.warning("Pipeline interrupted during %s", step_name)
        return 130

    logger.info("Pipeline finished (stage=%s)", args.stage)
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    sys.exit(main())
