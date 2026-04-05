"""Orchestration runner for complete author research pipeline.

Runs:
1. Author extraction from corpus
2. Biography enrichment
3. Timeline generation
4. Coverage analysis
"""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from hytools.config.settings import ValidationError as SettingsValidationError, load_config
from hytools.ingestion.discovery.author_extraction import AuthorExtractor, extract_authors_from_corpus
from hytools.ingestion.discovery.author_research import AuthorProfileManager
from hytools.ingestion.discovery.book_inventory import BookInventoryManager
from hytools.ingestion.enrichment.biography_enrichment import BiographyEnricher, ManualBiographyDatabase
from hytools.ingestion.aggregation.coverage_analysis import CoverageAnalyzer
from hytools.ingestion.aggregation.timeline_generation import TimelineGenerator
from hytools.ingestion._shared.research_config import get_research_config

logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False) -> None:
    """Setup logging configuration for terminal progress and future debugging."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Author research pipeline orchestrator",
    )

    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("data"),
        help="Corpus directory",
    )

    parser.add_argument(
        "--inventory-file",
        type=Path,
        default=Path("data/book_inventory.jsonl"),
        help="Book inventory JSONL file",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data"),
        help="Output directory for reports",
    )

    parser.add_argument(
        "--skip-extraction",
        action="store_true",
        help="Skip extraction phase (use existing profiles)",
    )

    parser.add_argument(
        "--skip-enrichment",
        action="store_true",
        help="Skip biography enrichment",
    )

    parser.add_argument(
        "--skip-timeline",
        action="store_true",
        help="Skip timeline generation",
    )

    parser.add_argument(
        "--skip-coverage",
        action="store_true",
        help="Skip coverage analysis",
    )

    parser.add_argument(
        "--wikipedia-lookups",
        type=int,
        default=50,
        help="Max Wikipedia lookups (rate limiting)",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config YAML (default: config/settings.yaml)",
    )
    parser.add_argument(
        "--exclude-dirs",
        nargs="+",
        default=None,
        help="Override research.exclude_dirs for extraction scope",
    )
    parser.add_argument(
        "--exclude-sources",
        nargs="+",
        default=None,
        help="Override research.exclude_sources for MongoDB-backed research scope",
    )
    parser.add_argument(
        "--metadata-patterns",
        nargs="+",
        default=None,
        help="Override research.metadata_patterns for extraction sidecar discovery",
    )
    parser.add_argument(
        "--error-threshold-pct",
        type=float,
        default=None,
        help="Override research.error_threshold_pct",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def _apply_cli_research_overrides(cfg: dict, args: argparse.Namespace) -> dict:
    updated = dict(cfg or {})
    research_cfg = dict(updated.get("research") or {})

    if args.exclude_dirs is not None:
        research_cfg["exclude_dirs"] = list(args.exclude_dirs)
    if args.exclude_sources is not None:
        research_cfg["exclude_sources"] = list(args.exclude_sources)
    if args.metadata_patterns is not None:
        research_cfg["metadata_patterns"] = list(args.metadata_patterns)
    if args.error_threshold_pct is not None:
        research_cfg["error_threshold_pct"] = float(args.error_threshold_pct)

    if research_cfg:
        updated["research"] = research_cfg
    return updated


def run_extraction_phase(
    corpus_dir: Path,
    inventory_file: Path,
    output_dir: Path,
    config: dict | None = None,
) -> AuthorProfileManager:
    """Run author extraction phase.

    Uses centralized research config (exclude_dirs, error_threshold_pct).
    """
    phase_start = time.perf_counter()
    logger.info("=" * 60)
    logger.info("PHASE 1: AUTHOR EXTRACTION")
    logger.info("=" * 60)

    research_cfg = get_research_config(config)
    exclude_dirs = research_cfg["exclude_dirs"]
    metadata_patterns = research_cfg["metadata_patterns"]
    error_threshold_pct = research_cfg["error_threshold_pct"]
    logger.info(
        "Config: corpus_dir=%s, exclude_dirs=%s, metadata_patterns=%s, error_threshold_pct=%s",
        corpus_dir,
        exclude_dirs,
        metadata_patterns,
        error_threshold_pct,
    )

    logger.info("Extracting authors from corpus (inventory + metadata + text patterns)...")
    extracted, error_count, total_processed = extract_authors_from_corpus(
        corpus_dir=corpus_dir,
        inventory_file=inventory_file,
        metadata_patterns=metadata_patterns,
        exclude_dirs=exclude_dirs,
        return_stats=True,
    )

    if total_processed > 0 and error_threshold_pct is not None and error_threshold_pct < 100:
        error_rate = 100.0 * error_count / total_processed
        if error_rate > error_threshold_pct:
            raise RuntimeError(
                f"Extraction error rate {error_rate:.1f}% exceeds threshold {error_threshold_pct}% "
                f"(errors={error_count}, processed={total_processed}). "
                "Check logs and config research.error_threshold_pct."
            )
        logger.info(f"Extraction errors: {error_count}/{total_processed} ({error_rate:.1f}%)")

    logger.info("Extraction complete: %d unique authors, %d errors in %d processed sources", len(extracted), error_count, total_processed)

    logger.info("Creating author profiles (min_confidence=0.6)...")
    extractor = AuthorExtractor()
    profiles = extractor.create_author_profiles(extracted, min_confidence=0.6)
    logger.info("Created %d author profiles from %d extractions", len(profiles), len(extracted))

    logger.info("Initializing AuthorProfileManager and persisting profiles...")
    manager = AuthorProfileManager(
        profiles_file=str(output_dir / "author_profiles.jsonl"),
        config=config or {},
    )
    manager.profiles.clear()
    for profile in profiles:
        manager.add_profile(profile)
    saved = manager.save_profiles()
    logger.info("Profiles persisted: %d saved", saved)

    elapsed = time.perf_counter() - phase_start
    logger.info("PHASE 1 complete in %.2f s | authors=%d, profiles=%d", elapsed, len(extracted), len(profiles))
    return manager


def run_enrichment_phase(
    manager: AuthorProfileManager,
    use_wikipedia: bool = True,
    max_lookups: int = 50,
) -> AuthorProfileManager:
    """Run biography enrichment phase.
    
    Args:
        manager: AuthorProfileManager with profiles to enrich
        use_wikipedia: Use Wikipedia for enrichment
        max_lookups: Max Wikipedia lookups (rate limiting)
        
    Returns:
        Updated AuthorProfileManager
    """
    phase_start = time.perf_counter()
    logger.info("=" * 60)
    logger.info("PHASE 2: BIOGRAPHY ENRICHMENT")
    logger.info("=" * 60)
    logger.info("Total profiles to process: %d (Wikipedia lookups max=%d)", len(manager.profiles), max_lookups)

    logger.info("Enriching from manual biography database...")
    manual_count = 0
    for profile_id, profile in manager.profiles.items():
        enriched = ManualBiographyDatabase.enrich_from_manual_data(profile)
        if enriched != profile:
            manual_count += 1
        manager.profiles[profile_id] = enriched
    logger.info("Manual enrichment: updated %d profiles", manual_count)

    if use_wikipedia:
        to_enrich = [
            p for p in manager.profiles.values()
            if not p.birth_year or not p.writing_period_start
        ]
        batch_size = min(len(to_enrich), max_lookups)
        logger.info("Enriching %d profiles from Wikipedia (capped at %d)...", len(to_enrich), batch_size)
        enricher = BiographyEnricher()
        enriched_profiles = enricher.enrich_batch(
            to_enrich[:max_lookups],
            max_profiles=max_lookups,
        )
        for profile in enriched_profiles:
            manager.profiles[profile.author_id] = profile
        logger.info("Wikipedia enrichment batch complete")
    else:
        logger.info("Wikipedia enrichment skipped (use_wikipedia=False)")

    logger.info("Saving updated profiles...")
    saved = manager.save_profiles()
    logger.info("Profiles saved: %d", saved)
    complete_profiles = len([p for p in manager.profiles.values() if p.profile_complete])
    elapsed = time.perf_counter() - phase_start
    logger.info("PHASE 2 complete in %.2f s | complete=%d/%d", elapsed, complete_profiles, len(manager.profiles))
    return manager


def run_timeline_phase(
    manager: AuthorProfileManager,
    output_dir: Path,
    config: dict | None = None,
) -> None:
    """Run timeline generation phase. All outputs go to MongoDB when config has database.mongodb_uri.
    
    Args:
        manager: AuthorProfileManager
        output_dir: Output directory (unused; retained for API compatibility)
        config: Pipeline config for MongoDB persistence
    """
    phase_start = time.perf_counter()
    logger.info("=" * 60)
    logger.info("PHASE 3: TIMELINE GENERATION")
    logger.info("=" * 60)
    logger.info("Authors in manager: %d", len(manager.profiles))

    generator = TimelineGenerator(manager)
    logger.info("Exporting timeline (include_historical=True)...")
    n = generator.export_timeline_json(include_historical=True, config=config)
    logger.info("Timeline: %s (%d events)", "saved to MongoDB" if n else "not persisted (no MongoDB)", n or 0)

    logger.info("Exporting period analysis CSV...")
    n = generator.export_period_analysis_csv(config=config)
    logger.info("Period analysis: %s", "saved to MongoDB" if n else "not persisted (no MongoDB)")

    logger.info("Exporting generation report...")
    n = generator.export_generation_report(config=config)
    logger.info("Generation report: %s", "saved to MongoDB" if n else "not persisted (no MongoDB)")

    periods = generator.generate_period_analysis(decade_grouping=True)
    logger.info("Authors by period:")
    for period in sorted(periods.keys()):
        logger.info("  %s: %d authors", period, len(periods[period]))
    elapsed = time.perf_counter() - phase_start
    logger.info("PHASE 3 complete in %.2f s", elapsed)


def run_coverage_phase(
    manager: AuthorProfileManager,
    inventory_file: Path,
    output_dir: Path,
    config: dict | None = None,
) -> None:
    """Run coverage analysis phase.
    
    Args:
        manager: AuthorProfileManager
        inventory_file: Book inventory file
        output_dir: Output directory
        config: Optional config dict (for MongoDB)
    """
    phase_start = time.perf_counter()
    logger.info("=" * 60)
    logger.info("PHASE 4: COVERAGE ANALYSIS")
    logger.info("=" * 60)

    logger.info("Loading book inventory from %s...", inventory_file)
    inventory_manager = BookInventoryManager(
        inventory_file=str(inventory_file),
        config=config or {},
    )
    logger.info("Inventory loaded: %d books", len(inventory_manager.books))

    analyzer = CoverageAnalyzer(manager, inventory_manager)
    logger.info("Generating comprehensive coverage analysis...")
    gaps = analyzer.generate_comprehensive_analysis()
    high_priority = [g for g in gaps if g.priority == "high"]
    logger.info("Analysis complete: %d total gaps, %d high priority", len(gaps), len(high_priority))

    logger.info("Exporting coverage gaps report...")
    n = analyzer.export_gaps_report(config=config)
    logger.info("Coverage gaps: %s", "saved to MongoDB" if n else "not persisted (no MongoDB)")

    logger.info("Exporting acquisition priority checklist...")
    n = analyzer.export_priority_checklist(config=config)
    logger.info("Acquisition priorities: %s", "saved to MongoDB" if n else "not persisted (no MongoDB)")

    logger.info("Coverage analysis summary:")
    logger.info("  Total gaps: %d | high: %d | medium/low: %d", len(gaps), len(high_priority), len(gaps) - len(high_priority))
    logger.info("  Top 5 priorities:")
    for gap in gaps[:5]:
        logger.info("    [%s] %s", gap.priority, gap.description)
    elapsed = time.perf_counter() - phase_start
    logger.info("PHASE 4 complete in %.2f s", elapsed)


def main():
    """Main orchestration function."""
    parser = _build_parser()
    args = parser.parse_args()

    setup_logging(debug=args.debug)
    pipeline_start = time.perf_counter()

    logger.info("Starting author research pipeline")
    cfg = {}
    config_path = args.config or Path("config/settings.yaml")
    if config_path.exists():
        try:
            cfg = load_config(str(config_path))
            logger.info("Loaded config from %s", config_path)
        except SettingsValidationError as e:
            raise RuntimeError(f"Invalid config {config_path}: {e}") from e
        except Exception as e:
            logger.warning("Could not load config %s: %s; using defaults", config_path, e)
    else:
        logger.info("No config file at %s; using defaults", config_path)

    cfg = _apply_cli_research_overrides(cfg, args)
    research_cfg = get_research_config(cfg)
    logger.info(
        "Research config: exclude_dirs=%s, exclude_sources=%s, metadata_patterns=%s, error_threshold_pct=%s",
        research_cfg["exclude_dirs"],
        research_cfg["exclude_sources"],
        research_cfg["metadata_patterns"],
        research_cfg["error_threshold_pct"],
    )

    use_mongodb = bool(cfg.get("database", {}).get("mongodb_uri") or cfg.get("database", {}).get("use_mongodb"))
    if use_mongodb:
        output_dir = Path(cfg.get("paths", {}).get("log_dir", "data/logs"))
        logger.info("Using MongoDB for persistence; output_dir=%s", output_dir)
    else:
        output_dir = args.output_dir
        logger.info("MongoDB not configured; using local output_dir=%s", output_dir)

    logger.info("Pipeline inputs: corpus_dir=%s, inventory_file=%s", args.corpus_dir, args.inventory_file)
    logger.info("Skip flags: extraction=%s, enrichment=%s, timeline=%s, coverage=%s",
                args.skip_extraction, args.skip_enrichment, args.skip_timeline, args.skip_coverage)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: Extraction
    if not args.skip_extraction:
        manager = run_extraction_phase(
            corpus_dir=args.corpus_dir,
            inventory_file=args.inventory_file,
            output_dir=output_dir,
            config=cfg,
        )
    else:
        logger.info("Skipping extraction; loading existing author profiles...")
        manager = AuthorProfileManager(
            profiles_file=str(output_dir / "author_profiles.jsonl"),
            config=cfg,
        )
        logger.info("Loaded %d existing profiles", len(manager.profiles))
    
    # Phase 2: Enrichment
    if not args.skip_enrichment:
        manager = run_enrichment_phase(
            manager=manager,
            use_wikipedia=True,
            max_lookups=args.wikipedia_lookups,
        )
    
    # Phase 3: Timeline
    if not args.skip_timeline:
        run_timeline_phase(
            manager=manager,
            output_dir=output_dir,
            config=cfg,
        )
    
    # Phase 4: Coverage
    if not args.skip_coverage:
        run_coverage_phase(
            manager=manager,
            inventory_file=args.inventory_file,
            output_dir=output_dir,
            config=cfg,
        )
    
    total_elapsed = time.perf_counter() - pipeline_start
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    logger.info(
        "Total time: %.2f s | profiles=%d | outputs in MongoDB",
        total_elapsed,
        len(manager.profiles),
    )
    if use_mongodb:
        logger.info("All author research outputs stored in MongoDB (no local files).")


def main_with_logging() -> None:
    """Entry point that catches and logs any unhandled exception for debugging."""
    try:
        main()
    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        raise


if __name__ == "__main__":
    main_with_logging()
