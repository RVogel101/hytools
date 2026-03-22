"""Tests for metadata schema and dialect tagging (moved from WesternArmenianLLM)."""

import json
from pathlib import Path
from datetime import datetime

from hytools.ingestion._shared.metadata import (
    TextMetadata,
    DialectSubcategory,
    Region,
    SourceType,
    ContentType,
)
from hytools.ingestion.enrichment.metadata_tagger import CorpusMetadataTagger


def test_western_wikipedia_metadata():
    """Test Western Armenian Wikipedia metadata factory."""
    meta = TextMetadata.western_wikipedia("Test Article", datetime.now().isoformat())

    assert meta.dialect_subcategory == DialectSubcategory.WESTERN_DIASPORA_GENERAL
    assert meta.source_language_code == "hyw"
    assert meta.source_name == "Wikipedia (hyw)"
    assert meta.source_type == SourceType.ENCYCLOPEDIA


def test_eastern_wikipedia_metadata():
    """Test Eastern Armenian Wikipedia metadata factory."""
    meta = TextMetadata.eastern_wikipedia("Test Article", datetime.now().isoformat())

    assert meta.dialect_subcategory == DialectSubcategory.EASTERN_HAYASTAN
    assert meta.source_language_code == "hye"
    assert meta.source_name == "Wikipedia (hye)"
    assert meta.region == Region.ARMENIA
    assert meta.confidence_region == 0.85


def test_metadata_serialization():
    """Test metadata to_dict and JSON serialization."""
    meta = TextMetadata.western_diaspora_newspaper(
        source_name="Aztag Daily",
        region=Region.LEBANON,
        extraction_date=datetime.now().isoformat(),
    )

    data = meta.to_dict()

    assert data["dialect_subcategory"] == "western_diaspora_general"
    assert data["region"] == "lebanon"
    assert data["source_type"] == "newspaper"
    assert data["content_type"] == "article"

    json_str = json.dumps(data)
    decoded = json.loads(json_str)
    assert decoded["dialect_subcategory"] == "western_diaspora_general"


def test_eastern_news_agency_metadata():
    """Test Eastern news agency metadata factory."""
    meta = TextMetadata.eastern_news_agency(
        "Armenpress",
        extraction_date=datetime.now().isoformat(),
    )

    assert meta.dialect_subcategory == DialectSubcategory.EASTERN_HAYASTAN
    assert meta.source_language_code == "hye"
    assert meta.source_name == "Armenpress"
    assert meta.region == Region.ARMENIA
    assert meta.source_type == SourceType.NEWS_AGENCY


def test_corpus_metadata_tagger_configs():
    """Test that tagger has proper configs for major corpora."""
    tagger = CorpusMetadataTagger()

    assert "wikipedia/extracted" in tagger.CORPUS_CONFIGS
    wa_config = tagger.CORPUS_CONFIGS["wikipedia/extracted"]
    assert wa_config["dialect_subcategory"] == DialectSubcategory.WESTERN_DIASPORA_GENERAL
    assert wa_config["source_language_code"] == "hyw"

    assert "wikipedia_ea" in tagger.CORPUS_CONFIGS
    ea_config = tagger.CORPUS_CONFIGS["wikipedia_ea"]
    assert ea_config["dialect_subcategory"] == DialectSubcategory.EASTERN_HAYASTAN
    assert ea_config["source_language_code"] == "hye"
    assert ea_config["region"] == Region.ARMENIA

    assert "newspapers/aztag" in tagger.CORPUS_CONFIGS
    aztag_config = tagger.CORPUS_CONFIGS["newspapers/aztag"]
    assert aztag_config["region"] == Region.LEBANON

    assert "newspapers/horizon" in tagger.CORPUS_CONFIGS
    horizon_config = tagger.CORPUS_CONFIGS["newspapers/horizon"]
    assert horizon_config["region"] == Region.CANADA

    assert "news_ea/aravot" in tagger.CORPUS_CONFIGS
    aravot_config = tagger.CORPUS_CONFIGS["news_ea/aravot"]
    assert aravot_config["dialect_subcategory"] == DialectSubcategory.EASTERN_HAYASTAN
    assert aravot_config["source_language_code"] == "hye"

    assert "news_ea/russian_influence" in tagger.CORPUS_CONFIGS
    assert "news_ea/iran" in tagger.CORPUS_CONFIGS
    assert "armeno_turkish" in tagger.CORPUS_CONFIGS


def test_language_codes_correctly_assigned():
    """Verify language codes: hyw (Western), hye (Eastern), hy (undetermined)."""
    wa_wiki = TextMetadata.western_wikipedia("Test", datetime.now().isoformat())
    assert wa_wiki.source_language_code == "hyw"

    ea_wiki = TextMetadata.eastern_wikipedia("Test", datetime.now().isoformat())
    assert ea_wiki.source_language_code == "hye"

    ea_news = TextMetadata.eastern_news_agency("Armenpress")
    assert ea_news.source_language_code == "hye"

    wa_news = TextMetadata.western_diaspora_newspaper(
        "Aztag", Region.LEBANON
    )
    assert wa_news.source_language_code is None


def test_language_codes_hyw_and_hye_both_used():
    """Explicitly verify both hyw (Western) and hye (Eastern) are assigned."""
    assert TextMetadata.western_wikipedia("WA", "2026-01-01").source_language_code == "hyw"
    assert TextMetadata.eastern_wikipedia("EA", "2026-01-01").source_language_code == "hye"
