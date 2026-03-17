"""Book inventory management and coverage tracking.

Tracks Western Armenian canonical works and their representation in corpus.
Integrates data from WorldCat, Library of Congress, Archive.org, manual entries,
and MongoDB corpus scanning for discovered titles.
"""

from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Armenian Unicode range
_ARMENIAN_RE = re.compile(r"[\u0530-\u058F]+")

# Context markers that indicate a following phrase is a book/manuscript title.
# Includes Western (WA) and Eastern (EA) Armenian plus Latin for mixed text.
_TITLE_CONTEXT_MARKERS = [
    # WA/EA shared
    "\u056f\u0561\u0580\u0564",       # kard (read)
    "\u0563\u056b\u0580\u0584",       # girkʿ (book)
    "\u0571\u0565\u0580\u0561\u0563\u056b\u0580",   # dzeragir (manuscript)
    "\u0570\u0580\u0561\u0569\u0561\u0580\u0561\u056f",  # hratarak (publish)
    "\u0563\u0580\u0561\u056e",       # grats (wrote)
    "\u0544\u0561\u0569\u0565\u0561\u0576",   # matian (manuscript/codex)
    "\u0536\u0578\u0572\u0578\u0582\u056e\u0561\u0581\u0582",  # zhoghovatsou (collection)
    # Latin (mixed text)
    "read", "book", "manuscript", "published", "wrote", "collection",
]

# "Book of" / "Collection of" patterns at start of title.
# WA = Western Armenian (classical), EA = Eastern Armenian (reformed).
_BOOK_OF_PATTERNS = [
    re.compile("^\u0563\u056b\u0580\u0584\\s"),   # Girkʿ (book) — WA/EA same
    re.compile("^\u0536\u0578\u0572\u0578\u0582\u056e\u0561\u0581\u0582\\s"),  # Zhoghovatsou — WA/EA same
    re.compile("^\u054a\u0561\u0569\u0574\u0582\u0569\u056b\u0582\u0576"),   # Patmutʿiwn (history) — WA
    re.compile("^\u054a\u0561\u0569\u0574\u0582\u0569\u0575\u0582\u0576"),   # Patmutʿyun — EA reformed
    re.compile("^\u054f\u0561\u0563\u0565\u0580"),   # Tagher (poems) — WA/EA same
    re.compile("^\u054f\u0561\u0563\u0565\u0580\u0563\u0582\u0569\u056b\u0582\u0576"),   # Taghergutʿiwn — WA
    re.compile("^\u054f\u0561\u0563\u0565\u0580\u0563\u0582\u0569\u0575\u0582\u0576"),   # Taghergutʿyun — EA reformed
    re.compile("^\u0535\u0580\u056f\u0565\u0580\\s"),  # Yerker (works) — WA/EA same
]

# Armenian guillemets for quoted titles
_ARMENIAN_QUOTE_OPEN = "\u00AB"   # «
_ARMENIAN_QUOTE_CLOSE = "\u00BB"  # »

# Common non-book entities to exclude. Includes WA, EA, and Latin.
_EXCLUDE_PERSON_PREFIXES = (
    "\u054e\u0580\u0564.", "\u0564\u0578\u056f.",  # Vrd., Dok. — WA/EA
)
_EXCLUDE_PLACES = {
    # WA (classical)
    "\u054a\u0567\u0575\u0580\u0578\u0582\u0569",   # Peyrouth (Beirut)
    "\u054a\u0578\u056c\u056b\u057d",         # Bolis (Istanbul)
    "\u0553\u0561\u0580\u056b\u0566",         # Bariz (Paris)
    "\u0540\u0561\u056c\u0567\u057a",         # Halep (Aleppo)
    "\u0535\u0580\u0565\u0582\u0561\u0576",         # Yerevan (WA classical)
    "\u0544\u0578\u0576\u0569\u0580\u0567\u0561\u056c",  # Montreal
    "\u0546\u056b\u0582 \u0535\u0578\u0580\u0584",  # New York
    # EA (reformed)
    "\u0532\u0565\u0575\u0580\u0582\u0569",   # Բեյրութ (Beirut)
    "\u0535\u0580\u0565\u057e\u0561\u0576",   # Երևան (Yerevan)
    "\u0546\u0575\u0582 \u0545\u0578\u0580\u0584",  # Նյու Յորք (New York)
    # Latin
    "peyrouth", "beirut", "bolis", "istanbul", "bariz", "paris",
    "halep", "aleppo", "yerevan", "montreal", "new york",
}
_EXCLUDE_INSTITUTIONS = {
    # WA
    "\u0544\u056d\u056b\u0569\u0561\u0580\u0565\u0561\u0576",  # Mekhitarean
    "\u0546\u0582\u054a\u0561\u0580\u0565\u0561\u0576",       # Nubarean
    # EA (reformed -յ-)
    "\u0544\u056d\u056b\u0569\u0561\u0580\u0575\u0561\u0576",  # Մխիթարյան
    "\u0546\u0582\u054a\u0561\u0580\u0575\u0561\u0576",       # Նուպարյան
    # Latin
    "mekhitarean", "nubarean",
}


class CoverageStatus(str, Enum):
    """Coverage status of a book in the corpus."""
    IN_CORPUS = "in_corpus"  # Full text in corpus
    PARTIALLY_SCANNED = "partially_scanned"  # Some pages/sections
    MISSING = "missing"  # Known but not in corpus
    COPYRIGHTED = "copyrighted"  # Rights unknown/restricted
    ACQUIRED = "acquired"  # In corpus but not yet processed
    OUT_OF_PRINT = "out_of_print"  # No online source found


class ContentType(str, Enum):
    """Type of content."""
    NOVEL = "novel"
    POETRY_COLLECTION = "poetry_collection"
    SHORT_STORIES = "short_stories"
    ESSAYS = "essays"
    JOURNALISM = "journalism"
    ACADEMIC = "academic"
    HISTORICAL = "historical"
    RELIGIOUS = "religious"
    BIOGRAPHY = "biography"
    MEMOIR = "memoir"
    PLAY = "play"
    TRAVEL = "travel"
    ANTHOLOGY = "anthology"
    OTHER = "other"


class LanguageVariant(str, Enum):
    """Armenian language variant."""
    WESTERN = "western"  # Western Armenian
    EASTERN = "eastern"  # Eastern Armenian
    CLASSICAL = "classical"  # Classical Armenian
    MIXED = "mixed"  # Western/Eastern blend
    UNKNOWN = "unknown"


@dataclass
class BookAuthor:
    """Author information for a book."""
    name: str  # Primary name (Western Armenian preferred)
    birth_year: Optional[int] = None
    birth_place: Optional[str] = None
    death_year: Optional[int] = None
    author_id: Optional[str] = None  # Link to author profile (future)


@dataclass
class BookEdition:
    """A specific edition of a book."""
    isbn: Optional[str] = None
    isbn_13: Optional[str] = None
    year: Optional[int] = None
    publisher: Optional[str] = None
    publisher_location: Optional[str] = None
    edition_number: Optional[int] = None
    num_pages: Optional[int] = None
    source_language_code: str = "hyw"  # Default to Western Armenian
    notes: str = ""


@dataclass
class BookInventoryEntry:
    """Single book in inventory."""
    
    # Essential metadata
    title: str  # Title in Armenian script preferred
    title_transliteration: Optional[str] = None  # Romanized version
    authors: list[BookAuthor] = field(default_factory=list)
    
    # Publication info
    first_publication_year: Optional[int] = None
    editions: list[BookEdition] = field(default_factory=list)
    
    # Content classification
    content_type: ContentType = ContentType.OTHER
    language_variant: LanguageVariant = LanguageVariant.WESTERN
    
    # Corpus status
    coverage_status: CoverageStatus = CoverageStatus.MISSING
    estimated_word_count: Optional[int] = None
    
    # Source tracking
    worldcat_oclc: Optional[str] = None  # WorldCat OCLC number
    loc_control_number: Optional[str] = None  # Library of Congress
    isbn_primary: Optional[str] = None  # Best available ISBN
    archive_org_id: Optional[str] = None  # Archive.org identifier
    
    # Discovery sources
    source_discovered_from: list[str] = field(default_factory=list)  # ["WorldCat", "Wikipedia", "LOC", ...]
    confidence_score: float = 1.0  # 0-1, how confident in this entry
    
    # Tags and notes
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    
    # Metadata quality
    metadata_last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    data_entry_date: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = asdict(self)
        # Convert enums to strings
        data["coverage_status"] = self.coverage_status.value
        data["content_type"] = self.content_type.value
        data["language_variant"] = self.language_variant.value
        data["authors"] = [asdict(author) for author in self.authors]
        data["editions"] = [asdict(edition) for edition in self.editions]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BookInventoryEntry:
        """Reconstruct from dictionary (e.g. from MongoDB or JSONL)."""
        authors_data = data.get("authors", [])
        authors = [
            BookAuthor(
                name=a.get("name", ""),
                birth_year=a.get("birth_year"),
                birth_place=a.get("birth_place"),
                death_year=a.get("death_year"),
                author_id=a.get("author_id"),
            )
            for a in authors_data
        ]
        editions_data = data.get("editions", [])
        editions = [
            BookEdition(
                isbn=e.get("isbn"),
                isbn_13=e.get("isbn_13"),
                year=e.get("year"),
                publisher=e.get("publisher"),
                publisher_location=e.get("publisher_location"),
                edition_number=e.get("edition_number"),
                num_pages=e.get("num_pages"),
                source_language_code=e.get("source_language_code") or e.get("language_code", "hyw"),
                notes=e.get("notes", ""),
            )
            for e in editions_data
        ]
        return cls(
            title=data.get("title", ""),
            title_transliteration=data.get("title_transliteration"),
            authors=authors,
            first_publication_year=data.get("first_publication_year"),
            editions=editions,
            content_type=ContentType(data.get("content_type", "other")),
            language_variant=LanguageVariant(data.get("language_variant", "western")),
            coverage_status=CoverageStatus(data.get("coverage_status", "missing")),
            estimated_word_count=data.get("estimated_word_count"),
            worldcat_oclc=data.get("worldcat_oclc"),
            loc_control_number=data.get("loc_control_number"),
            isbn_primary=data.get("isbn_primary"),
            archive_org_id=data.get("archive_org_id"),
            source_discovered_from=data.get("source_discovered_from", []),
            confidence_score=float(data.get("confidence_score", 1.0)),
            tags=data.get("tags", []),
            notes=data.get("notes", ""),
        )


@dataclass
class BookInventorySummary:
    """Summary statistics for inventory."""
    total_books: int = 0
    books_in_corpus: int = 0
    books_partially_scanned: int = 0
    books_missing: int = 0
    books_copyrighted: int = 0
    books_acquired: int = 0
    
    total_estimated_words: int = 0
    words_in_corpus: int = 0
    coverage_percentage: float = 0.0
    
    books_by_type: dict[str, int] = field(default_factory=dict)
    books_by_author: dict[str, int] = field(default_factory=dict)
    books_by_period: dict[str, int] = field(default_factory=dict)
    
    generation_date: str = field(default_factory=lambda: datetime.now().isoformat())


class BookInventoryManager:
    """Manages book inventory data and operations.

    Requires MongoDB (config.database.mongodb_uri). If MongoDB is not configured,
    logs an error and raises RuntimeError; there is no JSONL fallback.
    """

    def __init__(
        self,
        inventory_file: str = "data/book_inventory.jsonl",
        config: Optional[dict] = None,
    ):
        """Initialize inventory manager.

        Args:
            inventory_file: Ignored; retained for API compatibility. All data is in MongoDB.
            config: Pipeline config with database.mongodb_uri, database.mongodb_database.
                   Required for load/save.
        """
        self.inventory_file = Path(inventory_file)
        self.config = config or {}
        self._use_mongodb = bool(
            self.config.get("database", {}).get("mongodb_uri")
        )
        self.books: list[BookInventoryEntry] = []
        if not self._use_mongodb:
            logger.error(
                "BookInventoryManager requires MongoDB. Set database.mongodb_uri in config. "
                "No JSONL fallback; use python -m ingestion.discovery.migrate_book_inventory to migrate existing JSONL."
            )
            raise RuntimeError(
                "BookInventoryManager requires MongoDB (database.mongodb_uri). No JSONL fallback."
            )
        self._load_inventory()
    
    def add_book(self, book: BookInventoryEntry) -> None:
        """Add a book to inventory."""
        self.books.append(book)
    
    def add_books_batch(self, books: list[BookInventoryEntry]) -> None:
        """Add multiple books."""
        self.books.extend(books)
    
    def find_by_title(self, title: str, fuzzy: bool = False) -> list[BookInventoryEntry]:
        """Find books by title."""
        matches = []
        title_lower = title.lower()
        for book in self.books:
            if fuzzy:
                if title_lower in book.title.lower() or (
                    book.title_transliteration and title_lower in book.title_transliteration.lower()
                ):
                    matches.append(book)
            else:
                if title.lower() == book.title.lower():
                    matches.append(book)
        return matches
    
    def find_by_author(self, author_name: str) -> list[BookInventoryEntry]:
        """Find books by author name."""
        matches = []
        author_lower = author_name.lower()
        for book in self.books:
            for author in book.authors:
                if author_lower in author.name.lower():
                    matches.append(book)
                    break
        return matches

    def scan_mongodb(
        self,
        config: dict | None = None,
        min_title_len: int = 3,
        max_title_len: int = 120,
        min_armenian_ratio: float = 0.5,
        min_confidence: float = 0.5,
    ) -> int:
        """Scan MongoDB corpus documents for book/manuscript titles and add to inventory."""
        try:
            from ingestion._shared.helpers import open_mongodb_client
        except ImportError:
            logger.warning("ingestion._shared.helpers not available; cannot scan MongoDB")
            return 0

        cfg = config or {}
        seen_titles: set[str] = {b.title.strip().lower() for b in self.books}
        added = 0

        def _score_candidate(title: str, source: str, context: str = "") -> float:
            t = title.strip()
            if not (min_title_len <= len(t) <= max_title_len):
                return 0.0
            armenian = sum(1 for c in t if "\u0530" <= c <= "\u058F")
            if armenian / max(len(t), 1) < min_armenian_ratio:
                return 0.0
            if t.startswith("http") or t.startswith("www.") or "/" in t[:10]:
                return 0.0
            score = 0.0
            if _ARMENIAN_QUOTE_OPEN in t or t.startswith('"'):
                score += 0.2
            for pat in _BOOK_OF_PATTERNS:
                if pat.search(t):
                    score += 0.3
                    break
            for marker in _TITLE_CONTEXT_MARKERS:
                if marker in context:
                    score += 0.4
                    break
            if source == "metadata":
                score += 0.3
            if 5 <= len(t) <= 60:
                score += 0.1
            t_lower = t.lower()
            for p in _EXCLUDE_PLACES:
                if p.lower() in t_lower or t_lower == p.lower():
                    score -= 0.5
            for p in _EXCLUDE_INSTITUTIONS:
                if p.lower() in t_lower:
                    score -= 0.5
            for p in _EXCLUDE_PERSON_PREFIXES:
                if t.startswith(p):
                    score -= 0.5
            return max(0.0, min(1.0, score))

        def _extract_quoted(text: str) -> list[str]:
            out = []
            for pat in [
                r"\u00AB([^\u00BB]+)\u00BB",
                r'"([^"]+)"',
            ]:
                matches = re.findall(pat, text)
                out.extend(m.strip() for m in matches if m.strip())
            return out

        with open_mongodb_client(cfg) as client:
            if client is None:
                logger.warning("MongoDB unavailable; skipping scan")
                return 0
            coll = client.db["documents"]
            cursor = coll.find(
                {"$or": [{"text": {"$exists": True, "$ne": ""}}, {"title": {"$exists": True, "$ne": ""}}]},
                {"source": 1, "title": 1, "text": 1},
            )
            processed = 0
            for doc in cursor:
                processed += 1
                source_name = doc.get("source", "unknown")
                meta_title = doc.get("title", "").strip()
                text = doc.get("text", "") or ""
                if meta_title and len(meta_title) >= min_title_len:
                    conf = _score_candidate(meta_title, "metadata", text[:500])
                    if conf >= min_confidence:
                        key = meta_title.lower()
                        if key not in seen_titles:
                            seen_titles.add(key)
                            self.add_book(
                                BookInventoryEntry(
                                    title=meta_title,
                                    coverage_status=CoverageStatus.MISSING,
                                    source_discovered_from=["MongoDB scan"],
                                    notes=f"From {source_name} (doc title)",
                                )
                            )
                            added += 1
                for quoted in _extract_quoted(text[:3000]):
                    conf = _score_candidate(quoted, "text", text[:500])
                    if conf >= min_confidence:
                        key = quoted.lower()
                        if key not in seen_titles:
                            seen_titles.add(key)
                            self.add_book(
                                BookInventoryEntry(
                                    title=quoted,
                                    coverage_status=CoverageStatus.MISSING,
                                    source_discovered_from=["MongoDB scan"],
                                    notes=f"From {source_name} (extracted)",
                                )
                            )
                            added += 1
                if processed % 5000 == 0:
                    logger.info("MongoDB scan: processed %d docs, added %d titles", processed, added)

        logger.info("MongoDB scan: added %d new titles to inventory", added)
        return added

    def get_summary(self) -> BookInventorySummary:
        """Generate summary statistics."""
        summary = BookInventorySummary(total_books=len(self.books))
        for book in self.books:
            if book.coverage_status == CoverageStatus.IN_CORPUS:
                summary.books_in_corpus += 1
            elif book.coverage_status == CoverageStatus.PARTIALLY_SCANNED:
                summary.books_partially_scanned += 1
            elif book.coverage_status == CoverageStatus.MISSING:
                summary.books_missing += 1
            elif book.coverage_status == CoverageStatus.COPYRIGHTED:
                summary.books_copyrighted += 1
            elif book.coverage_status == CoverageStatus.ACQUIRED:
                summary.books_acquired += 1
            if book.estimated_word_count:
                summary.total_estimated_words += book.estimated_word_count
                if book.coverage_status == CoverageStatus.IN_CORPUS:
                    summary.words_in_corpus += book.estimated_word_count
            ct = book.content_type.value
            summary.books_by_type[ct] = summary.books_by_type.get(ct, 0) + 1
            for author in book.authors:
                summary.books_by_author[author.name] = summary.books_by_author.get(author.name, 0) + 1
            if book.first_publication_year:
                decade = (book.first_publication_year // 10) * 10
                period_key = f"{decade}s"
                summary.books_by_period[period_key] = summary.books_by_period.get(period_key, 0) + 1
        if summary.total_estimated_words > 0:
            summary.coverage_percentage = round(
                (summary.words_in_corpus / summary.total_estimated_words) * 100, 2
            )
        return summary
    
    def save_inventory(self, output_file: Optional[str] = None) -> Path | int:
        """Save inventory to MongoDB."""
        if not self._use_mongodb:
            raise RuntimeError("BookInventoryManager requires MongoDB; cannot save.")
        try:
            from ingestion._shared.helpers import open_mongodb_client
        except ImportError:
            logger.error("ingestion._shared.helpers not available; cannot save to MongoDB")
            return 0
        with open_mongodb_client(self.config) as client:
            if client is None:
                logger.error("MongoDB unavailable; inventory not saved")
                return 0
            docs = [b.to_dict() for b in self.books]
            count = client.save_book_inventory(docs)
            logger.info("Saved %d books to MongoDB book_inventory", count)
            return count
    
    def export_to_csv(self, output_file: str = "data/book_inventory.csv") -> Path:
        """Export inventory to CSV checklist."""
        filepath = Path(output_file)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "title", "title_transliteration", "primary_author", "publication_year",
            "content_type", "language_variant", "coverage_status", "estimated_words",
            "worldcat_oclc", "isbn", "archive_org_id", "notes",
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for book in self.books:
                author_name = book.authors[0].name if book.authors else "Unknown"
                writer.writerow({
                    "title": book.title,
                    "title_transliteration": book.title_transliteration or "",
                    "primary_author": author_name,
                    "publication_year": book.first_publication_year or "",
                    "content_type": book.content_type.value,
                    "language_variant": book.language_variant.value,
                    "coverage_status": book.coverage_status.value,
                    "estimated_words": book.estimated_word_count or "",
                    "worldcat_oclc": book.worldcat_oclc or "",
                    "isbn": book.isbn_primary or "",
                    "archive_org_id": book.archive_org_id or "",
                    "notes": book.notes,
                })
        logger.info("Exported %d books to %s", len(self.books), filepath)
        return filepath
    
    def export_summary_report(self, output_file: str = "data/book_inventory_summary.json") -> Path:
        """Export summary report to JSON."""
        filepath = Path(output_file)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        summary = self.get_summary()
        report = {
            "timestamp": summary.generation_date,
            "total_books": summary.total_books,
            "by_status": {
                "in_corpus": summary.books_in_corpus,
                "partially_scanned": summary.books_partially_scanned,
                "missing": summary.books_missing,
                "copyrighted": summary.books_copyrighted,
                "acquired": summary.books_acquired,
            },
            "word_counts": {
                "total_estimated": summary.total_estimated_words,
                "in_corpus": summary.words_in_corpus,
                "coverage_percentage": summary.coverage_percentage,
            },
            "by_content_type": summary.books_by_type,
            "top_authors": dict(sorted(summary.books_by_author.items(), key=lambda x: x[1], reverse=True)[:20]),
            "by_publication_period": summary.books_by_period,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info("Exported summary report to %s", filepath)
        return filepath
    
    def _load_inventory(self) -> None:
        """Load existing inventory from MongoDB."""
        if not self._use_mongodb:
            return
        try:
            from ingestion._shared.helpers import open_mongodb_client
        except ImportError:
            logger.warning("ingestion._shared.helpers not available; cannot load from MongoDB")
            return
        with open_mongodb_client(self.config) as client:
            if client is None:
                logger.warning("MongoDB unavailable; starting with empty inventory")
                return
            docs = client.load_book_inventory()
            for d in docs:
                d.pop("_id", None)
                d.pop("_title_key", None)
                try:
                    self.books.append(BookInventoryEntry.from_dict(d))
                except Exception as e:
                    logger.warning("Skipping invalid book entry: %s", e)
            logger.info("Loaded %d books from MongoDB book_inventory", len(self.books))


if __name__ == "__main__":
    import logging
    from pathlib import Path
    logging.basicConfig(level=logging.INFO)
    config_path = Path("config/settings.yaml")
    config: dict = {}
    if config_path.exists():
        try:
            import yaml
            with open(config_path, encoding="utf-8") as fh:
                config = yaml.safe_load(fh) or {}
        except Exception as e:
            logging.warning("Could not load %s: %s", config_path, e)
    if not config.get("database", {}).get("mongodb_uri"):
        print("BookInventoryManager requires MongoDB. Set database.mongodb_uri in config/settings.yaml")
        raise SystemExit(1)
    manager = BookInventoryManager(config=config)
    sample_book = BookInventoryEntry(
        title="Տաղի ծաղ",
        title_transliteration="Tagh Tsagh",
        authors=[BookAuthor(name="Հայրենիկ Գաբրիելյան", birth_year=1920)],
        first_publication_year=1965,
        content_type=ContentType.POETRY_COLLECTION,
        coverage_status=CoverageStatus.MISSING,
        estimated_word_count=45000,
        source_discovered_from=["Manual"],
        notes="Classic Western Armenian poetry",
    )
    manager.add_book(sample_book)
    manager.save_inventory()
    manager.export_to_csv()
    manager.export_summary_report()
    print("✓ Book inventory initialized and sample book added")
