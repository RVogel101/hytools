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
from pathlib import Path

from ingestion.discovery.author_extraction import AuthorExtractor, extract_authors_from_corpus
from ingestion.discovery.author_research import AuthorProfileManager
from ingestion.discovery.book_inventory import BookInventoryManager
from ingestion.enrichment.biography_enrichment import BiographyEnricher, ManualBiographyDatabase
from ingestion.aggregation.coverage_analysis import CoverageAnalyzer
from ingestion.aggregation.timeline_generation import TimelineGenerator
from ingestion._shared.research_config import get_research_config

logger = logging.getLogger(__name__)


def setup_logging(debug: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def run_extraction_phase(
    corpus_dir: Path,
    inventory_file: Path,
    output_dir: Path,
    config: dict | None = None,
) -> AuthorProfileManager:
    """Run author extraction phase.

    Uses centralized research config (exclude_dirs, error_threshold_pct).
    """
    logger.info("=" * 60)
    logger.info("PHASE 1: AUTHOR EXTRACTION")
    logger.info("=" * 60)

    research_cfg = get_research_config(config)
    exclude_dirs = research_cfg["exclude_dirs"]
    metadata_patterns = research_cfg["metadata_patterns"]
    error_threshold_pct = research_cfg["error_threshold_pct"]

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

    logger.info(f"Extracted {len(extracted)} unique authors")
    
    # Create profiles
    extractor = AuthorExtractor()
    profiles = extractor.create_author_profiles(extracted, min_confidence=0.6)
    
    # Add to manager (uses MongoDB when config has database.mongodb_uri)
    manager = AuthorProfileManager(
        profiles_file=str(output_dir / "author_profiles.jsonl"),
        config=config or {},
    )
    
    for profile in profiles:
        manager.add_profile(profile)
    
    # Save
    manager.save_profiles()
    
    logger.info(f"Created {len(profiles)} author profiles")
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
    logger.info("=" * 60)
    logger.info("PHASE 2: BIOGRAPHY ENRICHMENT")
    logger.info("=" * 60)
    
    # First, enrich from manual database
    for profile_id, profile in manager.profiles.items():
        enriched = ManualBiographyDatabase.enrich_from_manual_data(profile)
        manager.profiles[profile_id] = enriched
    
    # Then Wikipedia (if requested)
    if use_wikipedia:
        enricher = BiographyEnricher()
        
        # Get profiles that need enrichment
        to_enrich = [
            p for p in manager.profiles.values()
            if not p.birth_year or not p.writing_period_start
        ]
        
        logger.info(f"Enriching {min(len(to_enrich), max_lookups)} profiles from Wikipedia")
        
        enriched_profiles = enricher.enrich_batch(
            to_enrich[:max_lookups],
            max_profiles=max_lookups,
        )
        
        # Update manager
        for profile in enriched_profiles:
            manager.profiles[profile.author_id] = profile
    
    # Save updated profiles
    manager.save_profiles()
    
    # Statistics
    complete_profiles = len([p for p in manager.profiles.values() if p.profile_complete])
    logger.info(f"Enriched profiles: {complete_profiles}/{len(manager.profiles)} complete")
    
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
    logger.info("=" * 60)
    logger.info("PHASE 3: TIMELINE GENERATION")
    logger.info("=" * 60)
    
    generator = TimelineGenerator(manager)
    
    n = generator.export_timeline_json(include_historical=True, config=config)
    logger.info("Timeline: %s", "saved to MongoDB" if n else "not persisted (no MongoDB)")
    
    n = generator.export_period_analysis_csv(config=config)
    logger.info("Period analysis: %s", "saved to MongoDB" if n else "not persisted (no MongoDB)")
    
    n = generator.export_generation_report(config=config)
    logger.info("Generation report: %s", "saved to MongoDB" if n else "not persisted (no MongoDB)")
    
    periods = generator.generate_period_analysis(decade_grouping=True)
    logger.info("Authors by period:")
    for period in sorted(periods.keys()):
        logger.info("  %s: %d authors", period, len(periods[period]))


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
    logger.info("=" * 60)
    logger.info("PHASE 4: COVERAGE ANALYSIS")
    logger.info("=" * 60)
    
    # Load inventory (uses MongoDB when config has database.mongodb_uri)
    inventory_manager = BookInventoryManager(
        inventory_file=str(inventory_file),
        config=config or {},
    )
    
    analyzer = CoverageAnalyzer(manager, inventory_manager)
    
    n = analyzer.export_gaps_report(config=config)
    logger.info("Coverage gaps: %s", "saved to MongoDB" if n else "not persisted (no MongoDB)")
    
    n = analyzer.export_priority_checklist(config=config)
    logger.info("Acquisition priorities (all + high/medium/low): %s", "saved to MongoDB" if n else "not persisted (no MongoDB)")
    
    # Print summary
    gaps = analyzer.generate_comprehensive_analysis()
    high_priority = [g for g in gaps if g.priority == "high"]
    
    logger.info(f"\nCoverage Analysis Summary:")
    logger.info(f"  Total gaps identified: {len(gaps)}")
    logger.info(f"  High priority: {len(high_priority)}")
    logger.info(f"  Top 5 priorities:")
    
    for gap in gaps[:5]:
        logger.info(f"    [{gap.priority}] {gap.description}")


def main():
    """Main orchestration function."""
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
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    
    args = parser.parse_args()
    
    setup_logging(debug=args.debug)
    
    # Load config for MongoDB
    cfg = {}
    config_path = args.config or Path("config/settings.yaml")
    if config_path.exists():
        import yaml
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    
    # When using MongoDB, direct file exports to log_dir (zero local storage)
    use_mongodb = bool(cfg.get("database", {}).get("mongodb_uri") or cfg.get("database", {}).get("use_mongodb"))
    if use_mongodb:
        output_dir = Path(cfg.get("paths", {}).get("log_dir", "data/logs"))
    else:
        output_dir = args.output_dir

    logger.info("Starting author research pipeline")
    logger.info(f"Corpus: {args.corpus_dir}")
    logger.info(f"Inventory: {args.inventory_file}")
    logger.info(f"Output: {output_dir}")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Phase 1: Extraction
    if not args.skip_extraction:
        manager = run_extraction_phase(
            corpus_dir=args.corpus_dir,
            inventory_file=args.inventory_file,
            output_dir=args.output_dir,
            config=cfg,
        )
    else:
        # Load existing profiles (from MongoDB or JSONL)
        logger.info("Loading existing author profiles...")
        manager = AuthorProfileManager(
            profiles_file=str(args.output_dir / "author_profiles.jsonl"),
            config=cfg,
        )
        logger.info(f"Loaded {len(manager.profiles)} profiles")
    
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
    
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    logger.info("All author research outputs stored in MongoDB (no local files).")


if __name__ == "__main__":
    main()
