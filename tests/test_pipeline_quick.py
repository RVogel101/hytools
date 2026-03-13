"""Quick test of research pipeline phases without corpus text scanning."""

from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from ingestion.discovery.author_extraction import AuthorExtractor
from ingestion.discovery.author_research import AuthorProfileManager
from ingestion.discovery.book_inventory import BookInventoryManager
from ingestion.enrichment.biography_enrichment import BiographyEnricher, ManualBiographyDatabase
from ingestion.aggregation.coverage_analysis import CoverageAnalyzer
from ingestion.aggregation.timeline_generation import TimelineGenerator


def main():
    """Run quick pipeline test."""
    output_dir = Path("data")
    inventory_file = output_dir / "book_inventory.jsonl"
    
    # =====================================================================
    # PHASE 1: AUTHOR EXTRACTION (inventory only, no text scanning)
    # =====================================================================
    logger.info("=" * 60)
    logger.info("PHASE 1: AUTHOR EXTRACTION (Inventory Only)")
    logger.info("=" * 60)
    
    extractor = AuthorExtractor()
    inventory_manager = BookInventoryManager(inventory_file=str(inventory_file))
    
    # Extract from inventory only
    extracted = extractor.extract_from_book_inventory(inventory_manager)
    logger.info(f"Extracted {len(extracted)} authors from book inventory")
    
    # Create profiles
    profiles = extractor.create_author_profiles(extracted, min_confidence=0.6)
    
    # Save profiles
    manager = AuthorProfileManager(profiles_file=str(output_dir / "author_profiles.jsonl"))
    for profile in profiles:
        manager.add_profile(profile)
    manager.save_profiles()
    
    logger.info(f"✓ Created {len(profiles)} author profiles")
    
    # =====================================================================
    # PHASE 2: BIOGRAPHY ENRICHMENT (manual DB only)
    # =====================================================================
    logger.info("=" * 60)
    logger.info("PHASE 2: BIOGRAPHY ENRICHMENT (Manual DB Only)")
    logger.info("=" * 60)
    
    manual_db = ManualBiographyDatabase()
    enriched_count = 0
    
    for profile_id, profile in manager.profiles.items():
        enriched = manual_db.enrich_from_manual_data(profile)
        if enriched:
            enriched_count += 1
    
    # Save enriched profiles
    manager.save_profiles()
    logger.info(f"✓ Enriched {enriched_count} profiles from manual database")
    
    # =====================================================================
    # PHASE 3: TIMELINE GENERATION
    # =====================================================================
    logger.info("=" * 60)
    logger.info("PHASE 3: TIMELINE GENERATION")
    logger.info("=" * 60)
    
    timeline_gen = TimelineGenerator(manager)
    
    # Generate timeline
    timeline = timeline_gen.generate_author_lifespans()
    timeline.extend(timeline_gen.generate_writing_periods())
    timeline_gen.add_historical_context(timeline)
    
    # Timeline/period/generation: saved to MongoDB when config has mongodb_uri (here config=None)
    n = timeline_gen.export_timeline_json(include_historical=True, config=None)
    logger.info("✓ Generated timeline with %d events (saved to MongoDB: %s)", len(timeline), bool(n))
    periods = timeline_gen.generate_period_analysis(decade_grouping=True)
    timeline_gen.export_period_analysis_csv(config=None)
    logger.info("✓ Analyzed %d time periods", len(periods))
    generations = timeline_gen.generate_generation_analysis()
    timeline_gen.export_generation_report(config=None)
    logger.info("✓ Classified %d literary generations", len(generations))
    
    # =====================================================================
    # PHASE 4: COVERAGE ANALYSIS
    # =====================================================================
    logger.info("=" * 60)
    logger.info("PHASE 4: COVERAGE ANALYSIS")
    logger.info("=" * 60)
    
    analyzer = CoverageAnalyzer(manager, inventory_manager)
    
    # Analyze all gap types
    author_gaps = analyzer.analyze_author_coverage()
    period_gaps = analyzer.analyze_period_coverage()
    genre_gaps = analyzer.analyze_genre_coverage()
    work_gaps = analyzer.analyze_work_coverage()
    
    logger.info(f"  Author gaps: {len(author_gaps)}")
    logger.info(f"  Period gaps: {len(period_gaps)}")
    logger.info(f"  Genre gaps: {len(genre_gaps)}")
    logger.info(f"  Work gaps: {len(work_gaps)}")
    
    # Generate comprehensive analysis
    all_gaps = analyzer.generate_comprehensive_analysis()
    
    # Export reports to MongoDB when config has mongodb_uri (here config=None)
    analyzer.export_gaps_report(config=None)
    analyzer.export_priority_checklist(config=None)
    high_priority = [g for g in all_gaps if g.priority == "high"]
    logger.info("✓ Identified %d coverage gaps (%d high priority)", len(all_gaps), len(high_priority))
    
    # =====================================================================
    # SUMMARY
    # =====================================================================
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Authors: {len(manager.profiles)}")
    logger.info(f"Timeline Events: {len(timeline)}")
    logger.info(f"Time Periods: {len(periods)}")
    logger.info(f"Generations: {len(generations)}")
    logger.info(f"Coverage Gaps: {len(all_gaps)}")
    
    print("\n✓ All phases completed successfully!")
    print(f"\nOutputs saved to {output_dir}:")
    print("  - author_profiles.jsonl")
    print("  - author_timeline.json")
    print("  - author_periods.csv")
    print("  - author_generations.json")
    print("  - coverage_gaps.json")
    print("  - acquisition_priorities.csv")
    if high_priority:
        print("  - high_priority_acquisitions.csv")


if __name__ == "__main__":
    main()
