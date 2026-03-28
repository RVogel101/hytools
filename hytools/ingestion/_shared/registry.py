"""Extraction tool registry and invocation interface.

This module provides a centralized registry of all extraction tools with metadata,
dependencies, and invocation helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Any
import sys


class ToolStatus(Enum):
    """Tool availability status."""
    AVAILABLE = "available"
    TESTING = "testing"
    DEPRECATED = "deprecated"


@dataclass
class ToolDependency:
    """Tool dependency specification."""
    name: str
    module: str = ""
    external: bool = False
    required: bool = True
    version_min: str = ""


@dataclass
class ExtractionToolSpec:
    """Metadata for an extraction tool."""
    name: str
    description: str
    module: str
    function: str
    inputs: list[str]
    outputs: list[str]
    status: ToolStatus = ToolStatus.AVAILABLE
    batch: int = 0
    dependencies: list[ToolDependency] = field(default_factory=list)
    notes: str = ""


class ExtractionRegistry:
    """Registry of extraction tools with invocation interface."""

    def __init__(self):
        self._tools: dict[str, ExtractionToolSpec] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the canonical extraction tool suite (all MongoDB-native)."""

        self._tools["import_anki_to_mongodb"] = ExtractionToolSpec(
            name="import_anki_to_mongodb",
            description="Import Anki cards from AnkiConnect into MongoDB",
            module="hytools.ingestion.extraction.import_anki_to_mongodb",
            function="main",
            inputs=["AnkiConnect (HTTP)"],
            outputs=["MongoDB cards collection"],
            status=ToolStatus.AVAILABLE,
            batch=1,
            dependencies=[ToolDependency(name="requests", required=True), ToolDependency(name="pymongo", required=True)],
            notes="Fetches Anki notes via AnkiConnect and stores them in MongoDB",
        )

        self._tools["validate_contract_alignment"] = ExtractionToolSpec(
            name="validate_contract_alignment",
            description="Validate corpus data integrity in MongoDB",
            module="hytools.ingestion.validation.validate_contract_alignment",
            function="run",
            inputs=["MongoDB documents collection"],
            outputs=["MongoDB metadata collection (validation report)"],
            status=ToolStatus.AVAILABLE,
            batch=2,
            dependencies=[ToolDependency(name="pymongo", required=True)],
            notes="Checks field presence, dialect tags, source distribution",
        )

        self._tools["export_corpus_overlap_fingerprints"] = ExtractionToolSpec(
            name="export_corpus_overlap_fingerprints",
            description="Detect near-duplicate documents using normalized content hashes",
            module="hytools.ingestion.validation.export_corpus_overlap_fingerprints",
            function="run",
            inputs=["MongoDB documents collection"],
            outputs=["MongoDB metadata collection (dedup report)"],
            status=ToolStatus.AVAILABLE,
            batch=3,
            dependencies=[ToolDependency(name="pymongo", required=True)],
            notes="Analyzes normalized_content_hash for cross-source near-duplicates",
        )

        self._tools["materialize_dialect_views"] = ExtractionToolSpec(
            name="materialize_dialect_views",
            description="Tag documents with canonical dialect_view field for fast filtered queries",
            module="hytools.ingestion.enrichment.materialize_dialect_views",
            function="run",
            inputs=["MongoDB documents collection"],
            outputs=["MongoDB documents (dialect_view field added)"],
            status=ToolStatus.AVAILABLE,
            batch=4,
            dependencies=[ToolDependency(name="pymongo", required=True)],
            notes="Sets dialect_view: wa, ea, mixed, unknown based on metadata",
        )

        self._tools["frequency_aggregator"] = ExtractionToolSpec(
            name="frequency_aggregator",
            description="Build word frequency list from MongoDB corpus",
            module="hytools.ingestion.aggregation.frequency_aggregator",
            function="run",
            inputs=["MongoDB documents collection"],
            outputs=["MongoDB word_frequencies collection"],
            status=ToolStatus.AVAILABLE,
            batch=5,
            dependencies=[ToolDependency(name="pymongo", required=True)],
            notes="Per-source weighted word frequencies stored in MongoDB",
        )

        self._tools["summarize_unified_documents"] = ExtractionToolSpec(
            name="summarize_unified_documents",
            description="Summarize corpus by source, dialect, and size",
            module="hytools.ingestion.aggregation.summarize_unified_documents",
            function="run",
            inputs=["MongoDB documents collection"],
            outputs=["MongoDB metadata collection (summary)"],
            status=ToolStatus.AVAILABLE,
            batch=6,
            dependencies=[ToolDependency(name="pymongo", required=True)],
            notes="Aggregation queries over MongoDB corpus",
        )

    def register_tool(self, spec: ExtractionToolSpec) -> None:
        """Register a new extraction tool."""
        self._tools[spec.name] = spec

    def get_tool(self, name: str) -> ExtractionToolSpec | None:
        """Get tool metadata by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[ExtractionToolSpec]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_tools_by_batch(self, batch: int) -> list[ExtractionToolSpec]:
        """List tools from a specific batch."""
        return [t for t in self._tools.values() if t.batch == batch]

    def list_available_tools(self) -> list[ExtractionToolSpec]:
        """List available (non-deprecated) tools."""
        return [t for t in self._tools.values() if t.status == ToolStatus.AVAILABLE]

    def get_pipeline_order(self) -> list[ExtractionToolSpec]:
        """Get recommended tool execution order based on dependencies."""
        max_batch = max((t.batch for t in self._tools.values()), default=0)
        tools = []
        for b in range(1, max_batch + 1):
            tools.extend(self.list_tools_by_batch(b))
        return [t for t in tools if t.status == ToolStatus.AVAILABLE]

    def to_dict(self) -> dict[str, Any]:
        """Export registry as dictionary."""
        return {
            "tools": {
                name: {
                    "name": tool.name,
                    "description": tool.description,
                    "module": tool.module,
                    "function": tool.function,
                    "inputs": tool.inputs,
                    "outputs": tool.outputs,
                    "status": tool.status.value,
                    "batch": tool.batch,
                    "dependencies": [
                        {"name": d.name, "required": d.required}
                        for d in tool.dependencies
                    ],
                    "notes": tool.notes,
                }
                for name, tool in self._tools.items()
            },
            "total_tools": len(self._tools),
            "batches": max(t.batch for t in self._tools.values()),
        }


# Global registry instance
_registry: ExtractionRegistry | None = None


def get_registry() -> ExtractionRegistry:
    """Get or create the global extraction registry."""
    global _registry
    if _registry is None:
        _registry = ExtractionRegistry()
    return _registry


def get_tool_spec(name: str) -> ExtractionToolSpec | None:
    """Get a tool spec by name from the global registry."""
    return get_registry().get_tool(name)


def list_all_tools() -> list[ExtractionToolSpec]:
    """List all available tools from the global registry."""
    return get_registry().list_available_tools()


def get_pipeline_execution_order() -> list[ExtractionToolSpec]:
    """Get recommended tool execution order."""
    return get_registry().get_pipeline_order()
