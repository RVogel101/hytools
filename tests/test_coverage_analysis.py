from __future__ import annotations

from hytools.ingestion.aggregation.coverage_analysis import CoverageAnalyzer, CoverageGap
from hytools.ingestion.discovery.author_research import AuthorProfileManager
from hytools.ingestion.discovery.book_inventory import BookAuthor, BookInventoryEntry, BookInventoryManager, ContentType, CoverageStatus


def test_build_inventory_coverage_summary_uses_book_inventory_counts(tmp_path):
    inventory_file = tmp_path / "inventory.jsonl"
    manager = BookInventoryManager(str(inventory_file))
    manager.add_book(
        BookInventoryEntry(
            title="In Corpus",
            authors=[BookAuthor(name="Author")],
            coverage_status=CoverageStatus.IN_CORPUS,
            estimated_word_count=1000,
            content_type=ContentType.NOVEL,
        )
    )
    manager.add_book(
        BookInventoryEntry(
            title="Missing",
            authors=[BookAuthor(name="Author")],
            coverage_status=CoverageStatus.MISSING,
            estimated_word_count=500,
            content_type=ContentType.ESSAYS,
        )
    )

    analyzer = CoverageAnalyzer(AuthorProfileManager(), manager)
    summary = analyzer.build_inventory_coverage_summary()

    assert summary["total_books"] == 2
    assert summary["books_in_corpus"] == 1
    assert summary["coverage_percentage"] == 66.67


def test_build_acquisition_query_prefers_title_author_and_year():
    analyzer = CoverageAnalyzer(AuthorProfileManager())
    gap = CoverageGap(
        gap_type="work",
        priority="high",
        description="Missing work",
        recommended_action="Acquire it",
        metadata={"title": "Book Title", "authors": "Author Name", "year": 1934},
    )

    query = analyzer.build_acquisition_query(gap)

    assert query == "Book Title Author Name 1934"


def test_build_backfill_targets_adds_expected_sources_for_work_gap():
    analyzer = CoverageAnalyzer(AuthorProfileManager())
    gap = CoverageGap(
        gap_type="work",
        priority="high",
        description="Missing work",
        recommended_action="Acquire it",
        metadata={"title": "Book Title", "authors": "Author Name", "year": 1934, "content_type": "poetry_collection"},
    )

    targets = analyzer.build_backfill_targets(gap)

    assert targets[0] == {"source": "worldcat", "query": "Book Title Author Name 1934"}
    assert any(target["source"] == "loc" for target in targets)
    assert any(target["source"] == "nayiri" for target in targets)


def test_analyze_work_coverage_skips_implausible_titles(tmp_path):
    inventory_file = tmp_path / "inventory.jsonl"
    manager = BookInventoryManager(str(inventory_file))
    manager.add_book(
        BookInventoryEntry(
            title="Վաղ տես",
            authors=[BookAuthor(name="Օ. Թունեան")],
            coverage_status=CoverageStatus.MISSING,
            content_type=ContentType.NOVEL,
        )
    )
    manager.add_book(
        BookInventoryEntry(
            title="Դավտի Մեծ Զmassage",
            authors=[BookAuthor(name="Ա. Շիրակ")],
            coverage_status=CoverageStatus.MISSING,
            content_type=ContentType.NOVEL,
        )
    )

    analyzer = CoverageAnalyzer(AuthorProfileManager(), manager)

    gaps = analyzer.analyze_work_coverage()

    assert len(gaps) == 1
    assert gaps[0].metadata["title"] == "Վաղ տես"