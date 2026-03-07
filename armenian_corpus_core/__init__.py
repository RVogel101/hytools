"""Armenian Corpus Core Package

Central package for canonical Armenian language corpus contracts, extraction, and
normalization utilities. Provides unified interfaces for both Lousardzag (Anki learning)
and WesternArmenianLLM (corpus scraping) projects.

Modules:
- extraction: ETL tools and registry (export, ingest, merge, validate, materialize)
- scraping: 16 source scrapers (newspapers, Wikipedia, Nayiri, Archive.org, etc.)
- anki: AnkiConnect client, config, and pull pipeline
- database: Corpus ingestion DB (16 tables), card/flashcard DB, adapters, telemetry, migrator
- linguistics: Phonetics, morphology, FSRS scheduler, dialect classifier, stemmer
- cleaning: Text normalization, deduplication, WA language filter, tokenizer

Version: 0.1.0-alpha
Status: Alpha (local development installation only)
"""

__version__ = "0.1.0-alpha"
__author__ = "Lousardzag Contributors"

# Import key components for easy access
try:
    from armenian_corpus_core.extraction.registry import (
        get_registry,
        get_tool_spec,
        list_all_tools,
        get_pipeline_execution_order,
        ExtractionRegistry,
    )
    from armenian_corpus_core.core_contracts import (
        DialectTag,
        DocumentRecord,
        LexiconEntry,
        PhoneticResult,
        normalize_text_for_hash,
        sha256_normalized,
    )
    from armenian_corpus_core import data_sources
    from armenian_corpus_core.anki import AnkiConnect, AnkiConnectError
    from armenian_corpus_core.database import CardDatabase, CorpusDatabase
    from armenian_corpus_core import linguistics
    from armenian_corpus_core import cleaning

    __all__ = [
        "get_registry",
        "get_tool_spec",
        "list_all_tools",
        "get_pipeline_execution_order",
        "ExtractionRegistry",
        "DialectTag",
        "DocumentRecord",
        "LexiconEntry",
        "PhoneticResult",
        "normalize_text_for_hash",
        "sha256_normalized",
        "data_sources",
        "AnkiConnect",
        "AnkiConnectError",
        "CardDatabase",
        "CorpusDatabase",
        "linguistics",
        "cleaning",
    ]
except ImportError:
    # Fallback if extraction or other submodules not available: only expose
    # names that are actually bound (version, author). Do not list submodules
    # in __all__ or "from armenian_corpus_core import *" will raise NameError.
    __all__ = ["__version__", "__author__"]
