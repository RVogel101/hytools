"""Runner for book inventory research and checklist generation.

Orchestrates:
1. Fetching book data from WorldCat
2. Populating inventory
3. Generating reports and checklists
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ingestion.discovery.book_inventory import (
    BookAuthor,
    BookInventoryEntry,
    BookInventoryManager,
    ContentType,
    CoverageStatus,
    LanguageVariant,
)
from ingestion.discovery.worldcat_searcher import (
    FALLBACK_ARMENIAN_BOOKS,
    WorldCatSearcher,
    WorldCatError,
)

logger = logging.getLogger(__name__)


def setup_logging(level: int = logging.INFO) -> None:
    """Configure logging."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def load_fallback_books(manager: BookInventoryManager) -> int:
    """Load fallback book database.
    
    Args:
        manager: BookInventoryManager instance
        
    Returns:
        Number of books loaded
    """
    logger.info("Loading fallback Armenian book database...")
    
    for book_data in FALLBACK_ARMENIAN_BOOKS:
        authors = [
            BookAuthor(name=author_data["name"])
            for author_data in book_data.get("authors", [{"name": "Unknown"}])
        ]
        
        content_type = ContentType(book_data.get("content_type", "other"))
        
        book = BookInventoryEntry(
            title=book_data.get("title", ""),
            title_transliteration=book_data.get("title_transliteration"),
            authors=authors,
            first_publication_year=book_data.get("publication_year"),
            content_type=content_type,
            language_variant=LanguageVariant.WESTERN,
            coverage_status=CoverageStatus.MISSING,
            source_discovered_from=["Fallback Database"],
            notes=book_data.get("notes", ""),
        )
        
        manager.add_book(book)
    
    logger.info(f"Loaded {len(FALLBACK_ARMENIAN_BOOKS)} books from fallback database")
    return len(FALLBACK_ARMENIAN_BOOKS)


def search_worldcat(manager: BookInventoryManager) -> int:
    """Search WorldCat and add results to inventory.
    
    Args:
        manager: BookInventoryManager instance
        
    Returns:
        Number of books added
    """
    logger.info("Searching WorldCat for Armenian books...")
    
    try:
        searcher = WorldCatSearcher(
            timeout=10,
            delay_between_requests=0.5,
            max_results_per_query=50,
        )
        
        books = searcher.search_armenian_books()
        manager.add_books_batch(books)
        
        logger.info(f"Added {len(books)} books from WorldCat")
        return len(books)
    
    except WorldCatError as e:
        logger.error(f"WorldCat search failed: {e}")
        logger.info("Falling back to local database...")
        return 0


def generate_reports(
    manager: BookInventoryManager,
    output_dir: str = "data",
) -> None:
    """Generate all reports and exports.
    
    When using MongoDB, saves to MongoDB only (no local files).
    Otherwise saves to JSONL, CSV, and summary JSON.
    
    Args:
        manager: BookInventoryManager instance
        output_dir: Output directory for reports (used when not MongoDB)
    """
    # Save main inventory (to MongoDB or JSONL)
    result = manager.save_inventory()
    if isinstance(result, int):
        logger.info("✓ Saved inventory to MongoDB (%d books)", result)
    else:
        logger.info("✓ Saved inventory: %s", result)
    
    # Skip file exports when using MongoDB (zero local storage)
    if getattr(manager, "_use_mongodb", False):
        return
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    logger.info("Generating file exports in %s...", output_dir)
    
    csv_file = output_path / "book_inventory.csv"
    manager.export_to_csv(str(csv_file))
    logger.info("✓ Exported CSV checklist: %s", csv_file)
    
    summary_file = output_path / "book_inventory_summary.json"
    manager.export_summary_report(str(summary_file))
    logger.info("✓ Exported summary report: %s", summary_file)


def print_summary(manager: BookInventoryManager) -> None:
    """Print summary to console.
    
    Args:
        manager: BookInventoryManager instance
    """
    summary = manager.get_summary()
    
    print("\n" + "=" * 70)
    print("BOOK INVENTORY SUMMARY")
    print("=" * 70)
    print(f"\nTotal Books: {summary.total_books}")
    print(f"  ✓ In Corpus:        {summary.books_in_corpus}")
    print(f"  ◐ Partially Scanned: {summary.books_partially_scanned}")
    print(f"  ✗ Missing:          {summary.books_missing}")
    print(f"  ⊘ Copyrighted:      {summary.books_copyrighted}")
    print(f"  ◄ Acquired:         {summary.books_acquired}")
    
    print(f"\nWord Counts:")
    print(f"  Total Estimated:    {summary.total_estimated_words:,} words")
    print(f"  In Corpus:          {summary.words_in_corpus:,} words")
    print(f"  Coverage:           {summary.coverage_percentage:.1f}%")
    
    if summary.books_by_type:
        print(f"\nBy Content Type (top 5):")
        for ct, count in sorted(
            summary.books_by_type.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]:
            print(f"  {ct.capitalize():20s} {count:3d} books")
    
    if summary.books_by_author:
        print(f"\nTop Authors (top 5):")
        for author, count in sorted(
            summary.books_by_author.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]:
            print(f"  {author:30s} {count:3d} books")
    
    if summary.books_by_period:
        print(f"\nBy Publication Period:")
        for period, count in sorted(summary.books_by_period.items()):
            print(f"  {period:10s} {count:3d} books")
    
    print("\n" + "=" * 70 + "\n")


def main() -> int:
    """Main entry point.
    
    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        description="Build Western Armenian book inventory and checklist",
    )
    
    parser.add_argument(
        "--worldcat",
        action="store_true",
        help="Search WorldCat for books",
    )
    parser.add_argument(
        "--fallback",
        action="store_true",
        default=True,
        help="Use fallback database if WorldCat unavailable",
    )
    parser.add_argument(
        "--output",
        default="data",
        help="Output directory for reports",
    )
    parser.add_argument(
        "--scan-mongodb",
        action="store_true",
        help="Scan MongoDB corpus for book/manuscript titles (uses context markers, quotation marks, excludes NER)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config YAML (for MongoDB connection); default: config/settings.yaml",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logging(log_level)
    
    # Load config for MongoDB (default: config/settings.yaml)
    cfg = {}
    if args.config and args.config.exists():
        import yaml
        with open(args.config, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    
    try:
        # Initialize manager (uses MongoDB when config has database.mongodb_uri; else JSONL fallback)
        manager = BookInventoryManager(
            inventory_file=f"{args.output}/book_inventory.jsonl",
            config=cfg,
        )
        
        books_added = 0
        
        # Scan MongoDB for titles if requested
        if args.scan_mongodb:
            scan_count = manager.scan_mongodb(config=cfg)
            books_added += scan_count
        
        # Try WorldCat if requested
        if args.worldcat:
            wc_count = search_worldcat(manager)
            books_added += wc_count
        
        # Load fallback if needed and requested
        if args.fallback and books_added == 0:
            fallback_count = load_fallback_books(manager)
            books_added += fallback_count
        elif args.fallback:
            # Always augment with fallback for initial dataset
            fallback_count = load_fallback_books(manager)
            books_added += fallback_count
        
        if len(manager.books) == 0:
            logger.error("No books in inventory")
            return 1
        
        # Generate reports
        generate_reports(manager, args.output)
        
        # Print summary
        print_summary(manager)
        
        logger.info("✓ Book inventory process completed successfully")
        return 0
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=args.debug)
        return 1


if __name__ == "__main__":
    sys.exit(main())
