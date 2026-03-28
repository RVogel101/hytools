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
    """Armenian dialect classification (matches core_contracts DialectTag)."""
    WESTERN_ARMENIAN = "western_armenian"
    EASTERN_ARMENIAN = "eastern_armenian"
    CLASSICAL_ARMENIAN = "classical_armenian"  # Grabar (ISO 639-3: xcl; sometimes labeled hyc)
    MIXED = "mixed"
    UNKNOWN = "unknown"


class DialectSubcategory(str, Enum):
    """Fine-grained dialect/register subcategories for clustering and analysis."""
    UNKNOWN = "unknown"
    ARMENO_TURKISH = "armeno_turkish"
    WESTERN_DIASPORA_GENERAL = "western_diaspora_general"
    WESTERN_LEBANON = "western_lebanon"
    WESTERN_CALIFORNIA = "western_california"
    WESTERN_FRANCE = "western_france"
    WESTERN_CANADA = "western_canada"
    WESTERN_ARGENTINA = "western_argentina"
    WESTERN_GREECE = "western_greece"
    WESTERN_AUSTRALIA = "western_australia"
    WESTERN_IRAQ = "western_iraq"
    WESTERN_SYRIA = "western_syria"
    WESTERN_BOLIS = "western_bolis"
    WESTERN_EGYPT = "western_egypt"
    WESTERN_SUDAN = "western_sudan"
    WESTERN_KALKUTA = "western_kalkuta"
    WESTERN_JERUSALEM = "western_jerusalem"
    CLASSICAL_LITURGICAL = "classical_liturgical"  # Grabar / liturgical
    EASTERN_YEREVAN = "eastern_yerevan"
    EASTERN_GYUMRI = "eastern_gyumri"
    EASTERN_MOSCOW = "eastern_moscow"
    EASTERN_TBILISI = "eastern_tbilisi"
    EASTERN_IRAN = "eastern_iran"
    EASTERN_HAYASTAN = "eastern_hayastan"
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
    IRAQ = "iraq"

    # Eastern Armenian (Soviet and post-Soviet)
    ARMENIA = "armenia"
    ARTZAH = "artzah"
    GEORGIA = "georgia"
    IRAN = "iran"
    SYRIA = "syria"

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


class WritingCategory(str, Enum):
    """Kind of writing / genre for metadata tagging (book, news, liturgical, etc.)."""
    BOOK = "book"
    MANUSCRIPT = "manuscript"
    SCIENTIFIC_PAPER = "scientific_paper"
    LITURGICAL = "liturgical"
    FICTION = "fiction"
    NON_FICTION = "non_fiction"
    HISTORY = "history"
    POLITICS = "politics"
    NEWS = "news"
    ACADEMIC = "academic"
    LITERATURE = "literature"
    ARTICLE = "article"
    UNKNOWN = "unknown"


class InternalLanguageCode(str, Enum):
    """Top-level language classification derived from text analysis."""
    ARMENIAN = "hy"
    ENGLISH = "eng"


class InternalLanguageBranch(str, Enum):
    """Fine-grained language branch derived from text analysis.

    For Armenian, distinguishes Western vs Eastern dialect using
    compute_wa_score().  English is a single branch.
    """
    WESTERN_ARMENIAN = "hye-w"
    EASTERN_ARMENIAN = "hye-e"
    ENGLISH = "eng"


@dataclass
class TextMetadata:
    """Comprehensive metadata for a text document."""

    # Required fields
    source_type: SourceType

    # Language code from the source (e.g. hyw, hye, en) — as declared by the data provider
    source_language_code: Optional[str] = None
    # Internally derived language code from text analysis (hy or eng)
    internal_language_code: Optional[str] = None
    # Internally derived language branch from text analysis (hye-w, hye-e, or eng)
    internal_language_branch: Optional[str] = None
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
    writing_category: Optional[WritingCategory] = None

    # Provenance
    collection: Optional[str] = None
    processor_version: str = "1.0"

    # Quality/confidence flags
    confidence_region: float = 0.8

    # Additional metadata
    extra: dict = field(default_factory=dict)

    # Clustering readiness
    feature_schema_version: str = "1.0"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["dialect_subcategory"] = (
            self.dialect_subcategory.value if self.dialect_subcategory else None
        )
        data["region"] = self.region.value if self.region else None
        data["source_type"] = self.source_type.value
        data["content_type"] = self.content_type.value
        data["writing_category"] = (
            self.writing_category.value if self.writing_category else None
        )
        return data

    @classmethod
    def western_wikipedia(cls, title: str, extraction_date: str) -> TextMetadata:
        """Factory for Western Armenian Wikipedia articles.

        source_language_code: hyw (ISO 639-3 Western).
        """
        return cls(
            dialect_subcategory=DialectSubcategory.WESTERN_DIASPORA_GENERAL,
            source_type=SourceType.ENCYCLOPEDIA,
            source_language_code="hyw",
            source_name="Wikipedia (hyw)",
            extraction_date=extraction_date,
            content_type=ContentType.ARTICLE,
        )

    @classmethod
    def eastern_wikipedia(cls, title: str, extraction_date: str) -> TextMetadata:
        """Factory for Eastern Armenian Wikipedia articles.

        source_language_code: hye (ISO 639-3 Eastern).
        """
        return cls(
            dialect_subcategory=DialectSubcategory.EASTERN_HAYASTAN,
            source_type=SourceType.ENCYCLOPEDIA,
            source_language_code="hye",
            source_name="Wikipedia (hye)",
            region=Region.ARMENIA,
            extraction_date=extraction_date,
            content_type=ContentType.ARTICLE,
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
            dialect_subcategory=DialectSubcategory.WESTERN_DIASPORA_GENERAL,
            source_type=SourceType.NEWSPAPER,
            source_name=source_name,
            region=region,
            publication_date=publication_date,
            extraction_date=extraction_date,
            content_type=ContentType.ARTICLE,
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
            dialect_subcategory=DialectSubcategory.EASTERN_HAYASTAN,
            source_type=SourceType.NEWS_AGENCY,
            source_language_code="hye",
            source_name=source_name,
            region=Region.ARMENIA,
            publication_date=publication_date,
            extraction_date=extraction_date,
            content_type=ContentType.ARTICLE,
            confidence_region=0.99,
        )

    @classmethod
    def historical_archive(
        cls,
        source_name: str,
        region: Optional[Region] = None,
        original_date: Optional[str] = None,
        extraction_date: Optional[str] = None,
        catalog_id: Optional[str] = None,
    ) -> TextMetadata:
        """Factory for historical documents from archives."""
        return cls(
            source_type=SourceType.ARCHIVE,
            source_name=source_name,
            region=region or Region.UNCERTAIN,
            original_date=original_date,
            extraction_date=extraction_date,
            catalog_id=catalog_id,
            content_type=ContentType.HISTORICAL,
        )
