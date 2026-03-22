"""Author research and profiling pipeline.

Builds comprehensive author profiles with:
- Biographical information (birth/death dates and places)
- Writing periods and genres
- Known works and corpus coverage
- Chronological analysis

Pipeline: author_extraction discovers author names from corpus/inventory/metadata
→ create_author_profiles() yields AuthorProfile objects → this module stores and
manages them (AuthorProfileManager). Enrichment: biography_enrichment, timeline_generation,
coverage_analysis. Orchestration: ingestion.research_runner.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class AuthorProfile:
    """Comprehensive profile for a single author."""
    
    # Identity
    author_id: str  # UUID or canonical name
    primary_name: str  # Name in Armenian script
    name_variants: list[str] = field(default_factory=list)  # Transliterations, alternate names
    
    # Biographical data
    birth_year: Optional[int] = None
    birth_place: Optional[str] = None
    death_year: Optional[int] = None
    death_place: Optional[str] = None
    
    # Writing period
    writing_period_start: Optional[int] = None
    writing_period_end: Optional[int] = None
    
    # Characteristics
    genres: list[str] = field(default_factory=list)  # poetry, novel, essay, etc.
    topics: list[str] = field(default_factory=list)  # diaspora, identity, war, etc.
    language_variant: str = "western"  # western, eastern, classical, mixed
    
    # Known works
    known_works_count: int = 0
    known_works: list[dict] = field(default_factory=list)  # [{title, year, type}, ...]
    
    # Corpus statistics
    corpus_texts_count: int = 0  # Number of texts in corpus
    corpus_total_words: int = 0  # Total words in corpus by this author
    corpus_coverage_percentage: float = 0.0  # % of known works in corpus
    
    # Research metadata
    research_sources: list[str] = field(default_factory=list)  # Wikipedia, LOC, etc.
    confidence_birth: float = 0.5  # 0-1 confidence in birth data
    confidence_death: float = 0.5
    confidence_writing_period: float = 0.5
    
    # Notes and flags
    notes: str = ""
    flags: list[str] = field(default_factory=list)  # canonical, major_figure, etc.
    
    # Metadata quality
    profile_complete: bool = False  # Has all major fields filled
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuthorProfile:
        """Reconstruct from dictionary (e.g. from MongoDB or JSONL)."""
        return cls(
            author_id=data.get("author_id", ""),
            primary_name=data.get("primary_name", ""),
            name_variants=data.get("name_variants", []),
            birth_year=data.get("birth_year"),
            birth_place=data.get("birth_place"),
            death_year=data.get("death_year"),
            death_place=data.get("death_place"),
            writing_period_start=data.get("writing_period_start"),
            writing_period_end=data.get("writing_period_end"),
            genres=data.get("genres", []),
            topics=data.get("topics", []),
            language_variant=data.get("language_variant", "western"),
            known_works_count=data.get("known_works_count", 0),
            known_works=data.get("known_works", []),
            corpus_texts_count=data.get("corpus_texts_count", 0),
            corpus_total_words=data.get("corpus_total_words", 0),
            corpus_coverage_percentage=float(data.get("corpus_coverage_percentage", 0.0)),
            research_sources=data.get("research_sources", []),
            confidence_birth=float(data.get("confidence_birth", 0.5)),
            confidence_death=float(data.get("confidence_death", 0.5)),
            confidence_writing_period=float(data.get("confidence_writing_period", 0.5)),
            notes=data.get("notes", ""),
            flags=data.get("flags", []),
            profile_complete=bool(data.get("profile_complete", False)),
        )
    
    @property
    def is_canonical(self) -> bool:
        """Check if author is marked as canonical."""
        return "canonical" in self.flags
    
    @property
    def writing_duration(self) -> Optional[int]:
        """Estimated duration of writing career in years."""
        if self.writing_period_start and self.writing_period_end:
            return self.writing_period_end - self.writing_period_start
        return None


@dataclass
class AuthorChronology:
    """Timeline entry for a single author."""
    year: int
    event_type: str  # birth, first_publication, major_work, death
    description: str
    work_title: Optional[str] = None


class AuthorProfileManager:
    """Manages author profile data and operations.
    
    Uses MongoDB when config has database.mongodb_uri; otherwise uses JSONL file.
    """
    
    def __init__(
        self,
        profiles_file: str = "data/author_profiles.jsonl",
        config: Optional[dict] = None,
    ):
        """Initialize author profile manager.
        
        Args:
            profiles_file: Path to JSONL profiles file (fallback when not using MongoDB)
            config: Pipeline config with database.mongodb_uri, database.mongodb_database.
                    If present and MongoDB is configured, load/save from MongoDB.
        """
        self.profiles_file = Path(profiles_file)
        self.profiles_file.parent.mkdir(parents=True, exist_ok=True)
        self.config = config or {}
        self._use_mongodb = bool(
            self.config.get("database", {}).get("mongodb_uri")
        )
        self.profiles: dict[str, AuthorProfile] = {}
        self._load_profiles()
    
    def add_profile(self, profile: AuthorProfile) -> None:
        """Add an author profile.
        
        Args:
            profile: AuthorProfile to add
        """
        self.profiles[profile.author_id] = profile
    
    def find_by_name(self, name: str, fuzzy: bool = True) -> list[AuthorProfile]:
        """Find authors by name.
        
        Args:
            name: Author name to search
            fuzzy: If True, use substring matching
            
        Returns:
            List of matching profiles
        """
        matches = []
        name_lower = name.lower()
        
        for profile in self.profiles.values():
            # Check primary name
            if fuzzy:
                if name_lower in profile.primary_name.lower():
                    matches.append(profile)
                    continue
            else:
                if name_lower == profile.primary_name.lower():
                    matches.append(profile)
                    continue
            
            # Check variants
            for variant in profile.name_variants:
                if fuzzy:
                    if name_lower in variant.lower():
                        matches.append(profile)
                        break
                else:
                    if name_lower == variant.lower():
                        matches.append(profile)
                        break
        
        return matches
    
    def find_by_period(self, start_year: int, end_year: int) -> list[AuthorProfile]:
        """Find authors active in a time period.
        
        Args:
            start_year: Start year (inclusive)
            end_year: End year (inclusive)
            
        Returns:
            List of matching profiles
        """
        matches = []
        
        for profile in self.profiles.values():
            if not profile.writing_period_start or not profile.writing_period_end:
                continue
            
            # Check if writing period overlaps with specified range
            if profile.writing_period_end >= start_year and profile.writing_period_start <= end_year:
                matches.append(profile)
        
        return matches
    
    def find_canonical_authors(self) -> list[AuthorProfile]:
        """Get all canonical/major authors.
        
        Returns:
            List of canonical author profiles
        """
        return [p for p in self.profiles.values() if p.is_canonical]
    
    def get_summary_statistics(self) -> dict:
        """Generate summary statistics across all authors.
        
        Returns:
            Dictionary with statistics
        """
        profiles = list(self.profiles.values())
        
        if not profiles:
            return {
                "total_authors": 0,
                "canonical_authors": 0,
                "time_span": None,
                "by_period": {},
                "by_genre": {},
                "total_known_works": 0,
                "corpus_coverage_avg": 0.0,
            }
        
        # Time span
        birth_years = [p.birth_year for p in profiles if p.birth_year]
        write_starts = [p.writing_period_start for p in profiles if p.writing_period_start]
        
        time_span = None
        if birth_years and write_starts:
            time_span = (min(birth_years), max([p.writing_period_end for p in profiles if p.writing_period_end]))
        
        # By period (decade of first major work)
        by_period = {}
        for profile in profiles:
            if profile.writing_period_start:
                decade = (profile.writing_period_start // 10) * 10
                period_key = f"{decade}s"
                by_period[period_key] = by_period.get(period_key, 0) + 1
        
        # By genre
        by_genre = {}
        for profile in profiles:
            for genre in profile.genres:
                by_genre[genre] = by_genre.get(genre, 0) + 1
        
        # Coverage
        avg_coverage = sum(p.corpus_coverage_percentage for p in profiles) / len(profiles) if profiles else 0.0
        
        return {
            "total_authors": len(profiles),
            "canonical_authors": len([p for p in profiles if p.is_canonical]),
            "time_span": time_span,
            "by_period": by_period,
            "by_genre": by_genre,
            "total_known_works": sum(p.known_works_count for p in profiles),
            "corpus_coverage_avg": round(avg_coverage, 2),
            "authors_with_incomplete_profiles": len([p for p in profiles if not p.profile_complete]),
        }
    
    def save_profiles(self, output_file: Optional[str] = None) -> int:
        """Save profiles to MongoDB. No local file output.
        
        When using MongoDB, saves to author_profiles collection and returns count.
        When MongoDB is not configured, logs a warning and returns 0 (no file written).
        
        Args:
            output_file: Ignored; retained for API compatibility.
            
        Returns:
            Number of profiles saved (MongoDB), or 0.
        """
        if self._use_mongodb:
            try:
                from hytool.ingestion._shared.helpers import open_mongodb_client
            except ImportError:
                logger.warning("ingestion._shared.helpers not available; cannot save to MongoDB")
                return 0
            with open_mongodb_client(self.config) as client:
                if client is None:
                    logger.warning("MongoDB unavailable; profiles not saved")
                    return 0
                docs = [p.to_dict() for p in self.profiles.values()]
                count = client.save_author_profiles(docs)
                logger.info("Saved %d author profiles to MongoDB author_profiles", count)
                return count
        logger.warning("MongoDB not configured; author profiles not persisted (no file output)")
        return 0
    
    def export_chronology_csv(self, output_file: Optional[str] = None) -> int:
        """Persist author chronology to MongoDB (schema: year, author, event, place, details). No file output.
        
        Args:
            output_file: Ignored; retained for API compatibility.
            
        Returns:
            Number of events saved to MongoDB, or 0 if MongoDB not configured.
        """
        events = []
        for profile in self.profiles.values():
            if profile.birth_year:
                events.append({
                    "year": profile.birth_year,
                    "author": profile.primary_name,
                    "event": "birth",
                    "place": profile.birth_place or "",
                    "details": f"Born in {profile.birth_place}" if profile.birth_place else "Birth",
                })
            if profile.writing_period_start:
                events.append({
                    "year": profile.writing_period_start,
                    "author": profile.primary_name,
                    "event": "first_publication",
                    "place": "",
                    "details": "First known publication",
                })
            if profile.writing_period_end:
                events.append({
                    "year": profile.writing_period_end,
                    "author": profile.primary_name,
                    "event": "last_publication",
                    "place": "",
                    "details": "Last known publication",
                })
            if profile.death_year:
                events.append({
                    "year": profile.death_year,
                    "author": profile.primary_name,
                    "event": "death",
                    "place": profile.death_place or "",
                    "details": f"Died in {profile.death_place}" if profile.death_place else "Death",
                })
        events.sort(key=lambda x: x["year"])
        if not self._use_mongodb:
            logger.warning("MongoDB not configured; chronology not persisted (no file output)")
            return 0
        try:
            from hytool.ingestion._shared.helpers import open_mongodb_client
        except ImportError:
            logger.warning("ingestion._shared.helpers not available; chronology not saved")
            return 0
        with open_mongodb_client(self.config) as client:
            if client is None:
                return 0
            count = client.save_author_chronology(events)
        logger.info("Saved %d chronology events to MongoDB author_chronology", count)
        return count
    
    def export_bibliography_jsonl(
        self,
        output_file: Optional[str] = None,
    ) -> int:
        """Persist author bibliography to MongoDB (schema: author, author_id, + work fields). No file output.
        
        Args:
            output_file: Ignored; retained for API compatibility.
            
        Returns:
            Number of bibliography entries saved to MongoDB, or 0 if MongoDB not configured.
        """
        entries = []
        for profile in self.profiles.values():
            for work in profile.known_works:
                entries.append({
                    "author": profile.primary_name,
                    "author_id": profile.author_id,
                    **work,
                })
        if not self._use_mongodb:
            logger.warning("MongoDB not configured; bibliography not persisted (no file output)")
            return 0
        try:
            from hytool.ingestion._shared.helpers import open_mongodb_client
        except ImportError:
            logger.warning("ingestion._shared.helpers not available; bibliography not saved")
            return 0
        with open_mongodb_client(self.config) as client:
            if client is None:
                return 0
            count = client.save_author_bibliography(entries)
        logger.info("Saved %d bibliography entries to MongoDB author_bibliography", count)
        return count
    
    def export_summary_report(self, output_file: Optional[str] = None) -> int:
        """Persist author research summary to MongoDB (single document). No file output.
        
        Args:
            output_file: Ignored; retained for API compatibility.
            
        Returns:
            1 if saved to MongoDB, 0 if MongoDB not configured.
        """
        summary = self.get_summary_statistics()
        summary["generated"] = datetime.now().isoformat()
        if not self._use_mongodb:
            logger.warning("MongoDB not configured; summary report not persisted (no file output)")
            return 0
        try:
            from hytool.ingestion._shared.helpers import open_mongodb_client
        except ImportError:
            logger.warning("ingestion._shared.helpers not available; summary not saved")
            return 0
        with open_mongodb_client(self.config) as client:
            if client is None:
                return 0
            client.save_author_research_summary(summary)
        logger.info("Saved author research summary to MongoDB author_research_summary")
        return 1
    
    def _load_profiles(self) -> None:
        """Load existing profiles from MongoDB. No local file read; MongoDB required for persistence."""
        if self._use_mongodb:
            try:
                from hytool.ingestion._shared.helpers import open_mongodb_client
            except ImportError:
                logger.warning("ingestion._shared.helpers not available; cannot load from MongoDB")
                return
            with open_mongodb_client(self.config) as client:
                if client is None:
                    logger.warning("MongoDB unavailable; starting with empty profiles")
                    return
                docs = client.load_author_profiles()
                for d in docs:
                    d.pop("_id", None)
                    try:
                        profile = AuthorProfile.from_dict(d)
                        self.profiles[profile.author_id] = profile
                    except Exception as e:
                        logger.warning("Skipping invalid profile: %s", e)
                logger.info("Loaded %d author profiles from MongoDB author_profiles", len(self.profiles))
            return
        logger.info("MongoDB not configured; starting with empty author profiles (no file read)")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Example usage
    manager = AuthorProfileManager()
    
    # Create sample profile
    profile = AuthorProfile(
        author_id="adeep1880",
        primary_name="Ա. Շիրակ",
        name_variants=["A. Shiraк", "Avetik Shiraк"],
        birth_year=1880,
        birth_place="Adana",
        death_year=1968,
        writing_period_start=1905,
        writing_period_end=1965,
        genres=["novel", "short_stories"],
        topics=["diaspora", "identity", "family"],
        known_works_count=15,
        corpus_coverage_percentage=60.0,
        flags=["canonical"],
        profile_complete=True,
    )
    
    manager.add_profile(profile)
    manager.save_profiles()
    manager.export_chronology_csv()
    manager.export_bibliography_jsonl()
    manager.export_summary_report()
    # All outputs go to MongoDB only; no local files written.
    print("✓ Author profile manager initialized with sample author (data in MongoDB)")

