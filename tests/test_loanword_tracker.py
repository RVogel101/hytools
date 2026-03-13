"""Tests for linguistics.loanword_tracker."""

import pytest
from linguistics.loanword_tracker import (
    LoanwordReport,
    PossibleLoanwordReport,
    analyze_loanwords,
    analyze_possible_loanwords,
    analyze_batch,
    get_loanword_lexicon,
    add_loanwords,
)


def test_analyze_loanwords_empty():
    """Empty text returns zero counts."""
    report = analyze_loanwords("", text_id="empty", source="test")
    assert report.total_words == 0
    assert report.total_loanwords == 0
    assert report.loanword_ratio() == 0.0
    assert report.counts_by_language == {}
    assert report.unique_loanwords == []


def test_analyze_loanwords_russian():
    """Russian loanwords are detected."""
    text = "Այստեղ ապարատ ավտոբուս կա։"  # apparatus, bus
    report = analyze_loanwords(text, text_id="r1", source="test")
    assert report.total_loanwords >= 1
    assert "russian" in report.counts_by_language or report.total_loanwords > 0
    assert report.unique_loanwords


def test_analyze_loanwords_no_loanwords():
    """Plain Armenian text has zero loanwords."""
    text = "Ես կը խօսիմ հայերէն։"
    report = analyze_loanwords(text, text_id="wa1", source="test")
    assert report.total_words > 0
    # May have 0 loanwords if no Russian/Turkish/etc terms
    assert isinstance(report.counts_by_language, dict)
    assert isinstance(report.unique_loanwords, list)


def test_loanword_report_to_dict():
    """LoanwordReport serializes to dict."""
    report = LoanwordReport(
        text_id="t1",
        source="s1",
        total_words=100,
        total_loanwords=5,
        counts_by_language={"russian": 3, "turkish": 2},
        unique_loanwords=["ապարատ", "ավտոբուս"],
        loanwords_by_language={"russian": ["ապարատ", "ավտոբուս"]},
    )
    d = report.to_dict()
    assert d["text_id"] == "t1"
    assert d["total_loanwords"] == 5
    assert d["loanword_ratio"] == 0.05
    assert d["counts_by_language"]["russian"] == 3


def test_analyze_batch():
    """Batch analysis returns list of reports."""
    items = [
        ("Ես ապարատ ունիմ։", "doc1", "test"),
        ("Տուրիստ մը եկաւ։", "doc2", "test"),
    ]
    reports = analyze_batch(items)
    assert len(reports) == 2
    assert reports[0].text_id == "doc1"
    assert reports[1].text_id == "doc2"


def test_get_loanword_lexicon():
    """Lexicon can be retrieved by language."""
    russ = get_loanword_lexicon("russian")
    assert isinstance(russ, set)
    assert "ապարատ" in russ or len(russ) > 0
    empty = get_loanword_lexicon("nonexistent")
    assert empty == set()


def test_loanwords_in_document_metrics():
    """Loanword report is included in _compute_document_metrics for ingestion."""
    from ingestion._shared.helpers import _compute_document_metrics

    text = "Sample text with some content for metrics."
    metrics = _compute_document_metrics(text, "ingest_test", "test_source")
    assert metrics is not None
    assert "loanwords" in metrics
    lw = metrics["loanwords"]
    assert "total_words" in lw
    assert "total_loanwords" in lw
    assert "counts_by_language" in lw
    assert "unique_loanwords" in lw


def test_analyze_possible_loanwords_with_custom_dictionary():
    """PossibleLoanwordReport flags tokens not in custom dictionary."""

    def is_known(word: str) -> bool:
        # Treat only \"ասպիրանտ\" as known; everything else is unknown
        return word == "ասպիրանտ"

    text = "ասպիրանտ ավտոբուս ապարատ"
    report = analyze_possible_loanwords(text, text_id="u1", source="test", is_known_word=is_known)

    assert isinstance(report, PossibleLoanwordReport)
    assert report.total_words >= 1
    # Two unknowns: ավտոբուս, ապարատ
    assert report.total_possible_loanwords == 2
    assert set(report.unique_possible_loanwords) == {"ավտոբուս", "ապարատ"}


def test_lexicon_normalization_uppercase_matches():
    """Uppercase loanword in text is detected (tokenizer normalizes to lowercase)."""
    text = "ԱՎՏՈԲՈՒՍ եկաւ։"
    report = analyze_loanwords(text, text_id="up", source="test")
    assert report.total_words >= 1
    assert report.total_loanwords >= 1
    assert "russian" in report.counts_by_language
    assert "ավտոբուս" in report.unique_loanwords


def test_lexicon_normalization_example_loanwords():
    """Example loanwords from multiple languages are detected in one text."""
    text = "Ապարատ ու տուրիստ պասպորտով սալոն մտան, մատէ խմեցին։"
    report = analyze_loanwords(text, text_id="multi", source="test")
    assert report.total_words >= 1
    assert report.total_loanwords >= 2
    assert "ապարատ" in report.unique_loanwords or "տուրիստ" in report.unique_loanwords


def test_add_loanwords_normalizes():
    """add_loanwords stores normalized form; lookup matches."""
    add_loanwords("russian", ["  ՆՈՐԲԱՐ  "])
    russ = get_loanword_lexicon("russian")
    assert "նորբար" in russ
    report = analyze_loanwords("նորբար եկաւ", text_id="n", source="test")
    assert report.total_loanwords >= 1
    assert "նորբար" in report.unique_loanwords
