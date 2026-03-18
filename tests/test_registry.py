"""Tests for ingestion._shared.registry module."""

from ingestion._shared.registry import (
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
        assert len(tools) == 6

    def test_all_tools_available(self):
        registry = ExtractionRegistry()
        available = registry.list_available_tools()
        assert len(available) == 6
        assert all(t.status == ToolStatus.AVAILABLE for t in available)

    def test_tool_names(self):
        registry = ExtractionRegistry()
        names = {t.name for t in registry.list_tools()}
        expected = {
            "import_anki_to_mongodb",
            "validate_contract_alignment",
            "export_corpus_overlap_fingerprints",
            "materialize_dialect_views",
            "frequency_aggregator",
            "summarize_unified_documents",
        }
        assert names == expected

    def test_get_tool(self):
        registry = ExtractionRegistry()

    def test_get_nonexistent_tool(self):
        registry = ExtractionRegistry()
        assert registry.get_tool("nonexistent") is None

    def test_list_tools_by_batch(self):
        registry = ExtractionRegistry()

    def test_pipeline_order(self):
        registry = ExtractionRegistry()
        order = registry.get_pipeline_order()
        batches = [t.batch for t in order]
        assert batches == sorted(batches)

    def test_register_custom_tool(self):
        registry = ExtractionRegistry()
        custom = ExtractionToolSpec(
            name="custom_tool",
            description="A custom tool",
            module="custom.module",
            function="run",
            inputs=["MongoDB documents"],
            outputs=["MongoDB results"],
            batch=7,
        )
        registry.register_tool(custom)
        assert registry.get_tool("custom_tool") is not None
        assert len(registry.list_tools()) == 7

    def test_to_dict(self):
        registry = ExtractionRegistry()

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
        spec = get_tool_spec("validate_contract_alignment")
        assert spec is not None
        assert spec.batch == 2

    def test_get_tool_spec_missing(self):
        assert get_tool_spec("not_a_tool") is None

    def test_list_all_tools(self):
        tools = list_all_tools()
        assert len(tools) == 6

    def test_get_pipeline_execution_order(self):
        order = get_pipeline_execution_order()
        assert len(order) == 6
        assert order[0].batch == 1
