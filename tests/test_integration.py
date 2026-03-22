"""Integration tests for package imports and top-level API."""

from hytools.core_contracts import DialectTag, DocumentRecord, LexiconEntry, PhoneticResult
from hytools.ingestion._shared.registry import (
    get_registry,
    get_tool_spec,
    list_all_tools,
    get_pipeline_execution_order,
)


class TestTopLevelImports:
    def test_version(self):
        import importlib.metadata
        v = importlib.metadata.version("armenian-corpus-core")
        assert v.startswith("0.1.0")  # e.g. 0.1.0-alpha or 0.1.0a0

    def test_contracts_importable(self):
        assert DialectTag is not None
        assert DocumentRecord is not None
        assert LexiconEntry is not None
        assert PhoneticResult is not None

    def test_registry_importable(self):
        assert get_registry is not None
        assert get_tool_spec is not None
        assert list_all_tools is not None
        assert get_pipeline_execution_order is not None

    def test_roundtrip_create_document(self):
        """Create a DocumentRecord via top-level imports and verify fields."""
        doc = DocumentRecord(
            document_id="integration-test-1",
            source_family="test",
            text="Integration test text",
            dialect_tag=DialectTag.WESTERN_ARMENIAN,
        )
        assert doc.document_id == "integration-test-1"
        assert doc.dialect_tag == DialectTag.WESTERN_ARMENIAN

    def test_registry_tools_match_modules(self):
        """All registered tools reference ingestion or cleaning modules."""
        for tool in list_all_tools():
            assert tool.module.startswith("ingestion.") or tool.module.startswith("cleaning.")

    def test_pipeline_order_covers_all_tools(self):
        order = get_pipeline_execution_order()
        all_tools = list_all_tools()
        assert set(t.name for t in order) == set(t.name for t in all_tools)


class TestCoreContractSubpackage:
    def test_hashing_from_subpackage(self):
        from hytools.core_contracts import normalize_text_for_hash, sha256_normalized
        h = sha256_normalized("test")
        assert len(h) == 64

    def test_types_from_subpackage(self):
        from hytools.core_contracts import DialectTag, DocumentRecord, LexiconEntry, PhoneticResult
        entry = LexiconEntry(lemma="test")
        assert entry.lemma == "test"
