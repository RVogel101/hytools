"""Discovery: catalog search (WorldCat), book inventory, author extraction and research."""

from hytools.ingestion.discovery.book_inventory import (
    BookAuthor,
    BookEdition,
    BookInventoryEntry,
    BookInventoryManager,
    BookInventorySummary,
    ContentType,
    CoverageStatus,
    LanguageVariant,
)
from hytools.ingestion.discovery.author_research import AuthorProfile, AuthorProfileManager
from hytools.ingestion.discovery.worldcat_searcher import (
    FALLBACK_ARMENIAN_BOOKS,
    WorldCatError,
    WorldCatSearcher,
)
from hytools.ingestion.discovery.author_extraction import AuthorExtractor, extract_authors_from_corpus

__all__ = [
    "AuthorProfile",
    "AuthorProfileManager",
    "AuthorExtractor",
    "extract_authors_from_corpus",
    "BookAuthor",
    "BookEdition",
    "BookInventoryEntry",
    "BookInventoryManager",
    "BookInventorySummary",
    "ContentType",
    "CoverageStatus",
    "LanguageVariant",
    "FALLBACK_ARMENIAN_BOOKS",
    "WorldCatError",
    "WorldCatSearcher",
]
