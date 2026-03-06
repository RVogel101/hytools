"""Extraction tools for Armenian corpus ETL pipeline.

This module provides:
- registry: Tool metadata registry and discovery API
- run_extraction_pipeline: End-to-end pipeline orchestration

Exposed APIs:
- get_registry(): Get the global tool registry
- get_tool_spec(name): Get metadata for a specific tool
- list_all_tools(): List all available tools
- get_pipeline_execution_order(): Get recommended execution order
- ExtractionRegistry: Registry class for programmatic access
"""

try:
    from armenian_corpus_core.extraction.registry import (
        get_registry,
        get_tool_spec,
        list_all_tools,
        get_pipeline_execution_order,
        ExtractionRegistry,
        ExtractionToolSpec,
        ToolStatus,
    )
    
    __all__ = [
        "get_registry",
        "get_tool_spec",
        "list_all_tools",
        "get_pipeline_execution_order",
        "ExtractionRegistry",
        "ExtractionToolSpec",
        "ToolStatus",
    ]
except ImportError as e:
    __all__ = []
    # Registry import failed - module may not be functional
    import warnings
    warnings.warn(f"Failed to import extraction registry: {e}", ImportWarning)
