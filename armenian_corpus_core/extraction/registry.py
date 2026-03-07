"""Extraction tool registry and invocation interface.

This module provides a centralized registry of all extraction tools with metadata,
dependencies, and invocation helpers. Tools can be located in various places
(lousardzag, central package, etc.) and are referenced by registry entry.
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
        """Register the canonical extraction tool suite (Batches 1-6)."""

        # Batch 2: Export core contracts
        self._tools["export_core_contracts_jsonl"] = ExtractionToolSpec(
            name="export_core_contracts_jsonl",
            description="Export lousardzag DB rows to core contract JSONL (LexiconEntry + DocumentRecord)",
            module="armenian_corpus_core.extraction.export_core_contracts_jsonl",
            function="main",
            inputs=["armenian_cards.db"],
            outputs=["export_lexicon_entries.jsonl", "export_document_records.jsonl"],
            status=ToolStatus.AVAILABLE,
            batch=2,
            dependencies=[
                ToolDependency(name="sqlite3", required=True),
            ],
            notes="Requires path to lousardzag DB; outputs core contracts",
        )

        # Batch 3: Validate contract alignment
        self._tools["validate_contract_alignment"] = ExtractionToolSpec(
            name="validate_contract_alignment",
            description="Validate cross-project contract alignment (lousardzag vs. WesternArmenianLLM)",
            module="armenian_corpus_core.extraction.validate_contract_alignment",
            function="main",
            inputs=["export_lexicon_entries.jsonl", "export_document_records.jsonl", "WA_migration_exports/"],
            outputs=["contract_alignment_report.json"],
            status=ToolStatus.AVAILABLE,
            batch=3,
            dependencies=[],
            notes="Validates schemas and cross-project compatibility",
        )

        # Batch 4: Ingest WA fingerprints
        self._tools["ingest_wa_fingerprints_to_contracts"] = ExtractionToolSpec(
            name="ingest_wa_fingerprints_to_contracts",
            description="Convert WesternArmenianLLM corpus fingerprints to DocumentRecord contracts",
            module="armenian_corpus_core.extraction.ingest_wa_fingerprints_to_contracts",
            function="main",
            inputs=["wa_fingerprints.csv"],
            outputs=["wa_fingerprint_document_records.jsonl"],
            status=ToolStatus.AVAILABLE,
            batch=4,
            dependencies=[],
            notes="Handles CSV → DocumentRecord conversion with dialect inference",
        )

        # Batch 5: Merge and deduplicate
        self._tools["merge_document_records"] = ExtractionToolSpec(
            name="merge_document_records",
            description="Merge and deduplicate DocumentRecord JSONL files (basic)",
            module="armenian_corpus_core.extraction.merge_document_records",
            function="main",
            inputs=["export_document_records.jsonl", "wa_fingerprint_document_records.jsonl"],
            outputs=["unified_document_records.jsonl"],
            status=ToolStatus.AVAILABLE,
            batch=5,
            dependencies=[],
            notes="Primary dedup: content_hash; fallback: document_id",
        )

        # Batch 6a: Extract fingerprint index
        self._tools["extract_fingerprint_index"] = ExtractionToolSpec(
            name="extract_fingerprint_index",
            description="Separate fingerprint-only records from content-bearing records",
            module="armenian_corpus_core.extraction.extract_fingerprint_index",
            function="main",
            inputs=["unified_document_records.jsonl"],
            outputs=["unified_document_records_content_only.jsonl", "unified_document_records_fingerprint_index.jsonl"],
            status=ToolStatus.AVAILABLE,
            batch=6,
            dependencies=[],
            notes="Option B: Separate Index for training safety",
        )

        # Batch 6b: Materialize dialect views
        self._tools["materialize_dialect_views"] = ExtractionToolSpec(
            name="materialize_dialect_views",
            description="Create dialect-specific materialized views (WA, EA, MIXED)",
            module="armenian_corpus_core.extraction.materialize_dialect_views",
            function="main",
            inputs=["unified_document_records.jsonl"],
            outputs=["materialized_wa_documents.jsonl", "materialized_ea_documents.jsonl", "materialized_mixed_documents.jsonl"],
            status=ToolStatus.AVAILABLE,
            batch=6,
            dependencies=[],
            notes="Option C: Hybrid materialization with derived views",
        )

        # Batch 6c: Profile-based merge
        self._tools["merge_document_records_with_profiles"] = ExtractionToolSpec(
            name="merge_document_records_with_profiles",
            description="Merge with configurable conflict resolution profiles (app-ready, corpus-ready)",
            module="armenian_corpus_core.extraction.merge_document_records_with_profiles",
            function="main",
            inputs=["export_document_records.jsonl", "wa_fingerprint_document_records.jsonl"],
            outputs=["unified_document_records_app-ready.jsonl", "unified_document_records_corpus-ready.jsonl"],
            status=ToolStatus.AVAILABLE,
            batch=6,
            dependencies=[],
            notes="Option C: Rule-based profiles for app vs. corpus use cases",
        )

        # Batch 6d: Summarize unified documents
        self._tools["summarize_unified_documents"] = ExtractionToolSpec(
            name="summarize_unified_documents",
            description="Generate summary statistics and metrics for unified document corpus",
            module="armenian_corpus_core.extraction.summarize_unified_documents",
            function="main",
            inputs=["unified_document_records.jsonl"],
            outputs=["corpus_summary_report.json", "statistics_by_dialect.json"],
            status=ToolStatus.AVAILABLE,
            batch=6,
            dependencies=[],
            notes="Generates corpus metrics and dialect distribution summaries",
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
        # Topological sort by batch number and logical dependencies
        tools = self.list_tools_by_batch(2) + \
                self.list_tools_by_batch(3) + \
                self.list_tools_by_batch(4) + \
                self.list_tools_by_batch(5) + \
                self.list_tools_by_batch(6)
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
