"""Tests for armenian_corpus_core.extraction.registry module."""

from armenian_corpus_core.extraction.registry import (
    ExtractionRegistry,
    ExtractionToolSpec,
    ToolStatus,
    get_pipeline_execution_order,
    get_registry,
    get_tool_spec,
    list_all_tools,
)


class TestExtractionRegistry:
    def test_default_tools_registered(self):
        registry = ExtractionRegistry()
        tools = registry.list_tools()
        assert len(tools) == 8

    def test_all_tools_available(self):
        registry = ExtractionRegistry()
        available = registry.list_available_tools()
        assert len(available) == 8
        assert all(t.status == ToolStatus.AVAILABLE for t in available)

    def test_tool_names(self):
        registry = ExtractionRegistry()
        names = {t.name for t in registry.list_tools()}
        expected = {
            "export_core_contracts_jsonl",
            "validate_contract_alignment",
            "ingest_wa_fingerprints_to_contracts",
            "merge_document_records",
            "extract_fingerprint_index",
            "materialize_dialect_views",
            "merge_document_records_with_profiles",
            "summarize_unified_documents",
        }
        assert names == expected

    def test_get_tool(self):
        registry = ExtractionRegistry()
        tool = registry.get_tool("export_core_contracts_jsonl")
        assert tool is not None
        assert tool.batch == 2
        assert tool.module == "armenian_corpus_core.extraction.export_core_contracts_jsonl"

    def test_get_nonexistent_tool(self):
        registry = ExtractionRegistry()
        assert registry.get_tool("nonexistent") is None

    def test_list_tools_by_batch(self):
        registry = ExtractionRegistry()
        batch2 = registry.list_tools_by_batch(2)
        assert len(batch2) == 1
        assert batch2[0].name == "export_core_contracts_jsonl"

        batch6 = registry.list_tools_by_batch(6)
        assert len(batch6) == 4

    def test_pipeline_order(self):
        registry = ExtractionRegistry()
        order = registry.get_pipeline_order()
        batches = [t.batch for t in order]
        # Batch numbers should be non-decreasing
        assert batches == sorted(batches)

    def test_register_custom_tool(self):
        registry = ExtractionRegistry()
        custom = ExtractionToolSpec(
            name="custom_tool",
            description="A custom tool",
            module="custom.module",
            function="run",
            inputs=["input.txt"],
            outputs=["output.txt"],
            batch=7,
        )
        registry.register_tool(custom)
        assert registry.get_tool("custom_tool") is not None
        assert len(registry.list_tools()) == 9

    def test_to_dict(self):
        registry = ExtractionRegistry()
        d = registry.to_dict()
        assert d["total_tools"] == 8
        assert d["batches"] == 6
        assert "tools" in d
        assert "export_core_contracts_jsonl" in d["tools"]

    def test_tool_has_inputs_outputs(self):
        registry = ExtractionRegistry()
        for tool in registry.list_tools():
            assert isinstance(tool.inputs, list)
            assert isinstance(tool.outputs, list)
            assert len(tool.outputs) > 0


class TestGlobalRegistryFunctions:
    def test_get_registry_singleton(self):
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_get_tool_spec(self):
        spec = get_tool_spec("merge_document_records")
        assert spec is not None
        assert spec.batch == 5

    def test_get_tool_spec_missing(self):
        assert get_tool_spec("not_a_tool") is None

    def test_list_all_tools(self):
        tools = list_all_tools()
        assert len(tools) == 8

    def test_get_pipeline_execution_order(self):
        order = get_pipeline_execution_order()
        assert len(order) == 8
        # First tool should be batch 2
        assert order[0].batch == 2
