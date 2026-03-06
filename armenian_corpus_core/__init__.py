"""Armenian Corpus Core Package

Central package for canonical Armenian language corpus contracts, extraction, and
normalization utilities. Provides unified interfaces for both Lousardzag (Anki learning)
and WesternArmenianLLM (corpus scraping) projects.

Modules:
- extraction: ETL tools and registry (export, ingest, merge, validate, materialize)

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
    
    __all__ = [
        "extraction",
        "get_registry",
        "get_tool_spec", 
        "list_all_tools",
        "get_pipeline_execution_order",
        "ExtractionRegistry",
    ]
except ImportError:
    # Fallback if extraction module not available
    __all__ = ["extraction"]
