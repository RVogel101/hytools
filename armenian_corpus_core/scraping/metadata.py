"""Unified metadata schema for all corpus sources (WA and EA).

Provides:
- Dialect/region tagging (western/eastern)
- Author/publication origin tracking
- Date handling (publication, extraction, etc.)
- Source provenance (urls, catalog ids, etc.)
- Content classification (article, literature, transcription, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional
from enum import Enum


class Dialect(str, Enum):
    """Armenian dialect classification."""
    WESTERN = "western"
    EASTERN = "eastern"
    MIXED = "mixed"


class DialectSubcategory(str, Enum):
    """Fine-grained dialect/register subcategories for clustering and analysis."""
    UNKNOWN = "unknown"
    ARMENO_TURKISH = "armeno_turkish"
    WESTERN_DIASPORA_GENERAL = "western_diaspora_general"
    EASTERN_HAYASTAN = "eastern_hayastan"
    EASTERN_RUSSIAN_INFLUENCE = "eastern_russian_influence"
    EASTERN_IRAN = "eastern_iran"
    EASTERN_OTHER = "eastern_other"


class Region(str, Enum):
    """Geographic origin regions for dialect sourcing."""
    # Western Armenian diaspora
    LEBANON = "lebanon"
    CALIFORNIA = "california"
    FRANCE = "france"
    CANADA = "canada"
    ARGENTINA = "argentina"
    GREECE = "greece"
    AUSTRALIA = "australia"
    WESTERN_OTHER = "western_other"

    # Eastern Armenian (Soviet and post-Soviet)
    ARMENIA = "armenia"
    NAGORNO_KARABAKH = "nagorno_karabakh"
    GEORGIA_EA = "georgia_ea"
    IRAN = "iran"
    SYRIA = "syria"
    EASTERN_OTHER = "eastern_other"

    # Unspecified or multi-region
    UNCERTAIN = "uncertain"
    MULTI_REGION = "multi_region"


class ContentType(str, Enum):
    """Type/genre of content."""
    ARTICLE = "article"
    LITERATURE = "literature"
    ACADEMIC = "academic"
    TRANSCRIPTION = "transcription"
    LEGAL = "legal"
    POEM = "poem"
    PROSE = "prose"
    HISTORICAL = "historical"
    RELIGIOUS = "religious"
    MIXED = "mixed"


class SourceType(str, Enum):
    """Primary source classification."""
    ENCYCLOPEDIA = "encyclopedia"
    LITERATURE = "literature"
    NEWSPAPER = "newspaper"
    NEWS_AGENCY = "news_agency"
    BLOG = "blog"
    SOCIAL_MEDIA = "social_media"
    ARCHIVE = "archive"
    LIBRARY = "library"
    ACADEMIC = "academic"
    HISTORICAL_COLLECTION = "historical_collection"
    WEBSITE = "website"


@dataclass
class TextMetadata:
    """Comprehensive metadata for a text document."""

    # Required fields
    dialect: Dialect
    source_type: SourceType

    # Language/Wikipedia code
    language_code: Optional[str] = None
    dialect_subcategory: Optional[DialectSubcategory] = None

    # Date fields
    extraction_date: Optional[str] = None
    publication_date: Optional[str] = None
    original_date: Optional[str] = None

    # Regional/geographic origin
    region: Optional[Region] = None
    author_origin: Optional[str] = None

    # Source reference
    source_name: str = ""
    source_url: Optional[str] = None
    catalog_id: Optional[str] = None

    # Content classification
    content_type: ContentType = ContentType.ARTICLE
    category: Optional[str] = None

    # Provenance
    collection: Optional[str] = None
    processor_version: str = "1.0"

    # Quality/confidence flags
    confidence_dialect: float = 1.0
    confidence_region: float = 0.8

    # Additional metadata
    extra: dict = field(default_factory=dict)

    # Clustering readiness
    feature_schema_version: str = "1.0"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["dialect"] = self.dialect.value
        data["dialect_subcategory"] = (
            self.dialect_subcategory.value if self.dialect_subcategory else None
        )
        data["region"] = self.region.value if self.region else None
        data["source_type"] = self.source_type.value
        data["content_type"] = self.content_type.value
        return data

    @classmethod
    def western_wikipedia(cls, title: str, extraction_date: str) -> TextMetadata:
        """Factory for Western Armenian Wikipedia articles (hyw)."""
        return cls(
            dialect=Dialect.WESTERN,
            dialect_subcategory=DialectSubcategory.WESTERN_DIASPORA_GENERAL,
            source_type=SourceType.ENCYCLOPEDIA,
            language_code="hyw",
            source_name="Wikipedia (hyw)",
            extraction_date=extraction_date,
            content_type=ContentType.ARTICLE,
            confidence_dialect=0.99,
        )

    @classmethod
    def eastern_wikipedia(cls, title: str, extraction_date: str) -> TextMetadata:
        """Factory for Eastern Armenian Wikipedia articles (hy)."""
        return cls(
            dialect=Dialect.EASTERN,
            dialect_subcategory=DialectSubcategory.EASTERN_HAYASTAN,
            source_type=SourceType.ENCYCLOPEDIA,
            language_code="hy",
            source_name="Wikipedia (hy)",
            region=Region.ARMENIA,
            extraction_date=extraction_date,
            content_type=ContentType.ARTICLE,
            confidence_dialect=0.95,
            confidence_region=0.85,
        )

    @classmethod
    def western_diaspora_newspaper(
        cls,
        source_name: str,
        region: Region,
        publication_date: Optional[str] = None,
        extraction_date: Optional[str] = None,
    ) -> TextMetadata:
        """Factory for diaspora newspaper articles (typically WA)."""
        return cls(
            dialect=Dialect.WESTERN,
            dialect_subcategory=DialectSubcategory.WESTERN_DIASPORA_GENERAL,
            source_type=SourceType.NEWSPAPER,
            source_name=source_name,
            region=region,
            publication_date=publication_date,
            extraction_date=extraction_date,
            content_type=ContentType.ARTICLE,
            confidence_dialect=0.90,
            confidence_region=0.95,
        )

    @classmethod
    def eastern_news_agency(
        cls,
        source_name: str,
        publication_date: Optional[str] = None,
        extraction_date: Optional[str] = None,
    ) -> TextMetadata:
        """Factory for Armenian news agencies (Armenpress, A1+, etc.)."""
        return cls(
            dialect=Dialect.EASTERN,
            dialect_subcategory=DialectSubcategory.EASTERN_HAYASTAN,
            source_type=SourceType.NEWS_AGENCY,
            language_code="hy",
            source_name=source_name,
            region=Region.ARMENIA,
            publication_date=publication_date,
            extraction_date=extraction_date,
            content_type=ContentType.ARTICLE,
            confidence_dialect=0.98,
            confidence_region=0.99,
        )

    @classmethod
    def historical_archive(
        cls,
        dialect: Dialect,
        source_name: str,
        region: Optional[Region] = None,
        original_date: Optional[str] = None,
        extraction_date: Optional[str] = None,
        catalog_id: Optional[str] = None,
    ) -> TextMetadata:
        """Factory for historical documents from archives."""
        return cls(
            dialect=dialect,
            dialect_subcategory=(
                DialectSubcategory.WESTERN_DIASPORA_GENERAL
                if dialect == Dialect.WESTERN
                else DialectSubcategory.EASTERN_OTHER
            ),
            source_type=SourceType.ARCHIVE,
            source_name=source_name,
            region=region or Region.UNCERTAIN,
            original_date=original_date,
            extraction_date=extraction_date,
            catalog_id=catalog_id,
            content_type=ContentType.HISTORICAL,
            confidence_dialect=0.85,
        )
