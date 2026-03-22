"""Shared utilities for scraping modules.

Consolidates MongoDB helpers, Western Armenian language classification,
Wikimedia dump processing, and common catalog I/O into a single import.

Sections
--------
- **MongoDB**: ``open_mongodb_client``, ``insert_or_skip``, ``load_catalog_from_mongodb``, ``save_catalog_to_mongodb``
- **WA classifier**: ``compute_wa_score``, ``is_western_armenian``, ``try_wa_filter``
- **Wikitext**: ``clean_wikitext``, ``is_redirect``, ``resolve_dump_date``, ``download_dump``
- **Newspaper splitter**: ``split_issue_into_articles``, ``ArticleChunk`` (for full-issue OCR blobs)
- **Logging**: ``log_stage``, ``log_item``
"""

from __future__ import annotations

import bz2
import json
import logging
import re
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, List

import requests

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
#  MongoDB helpers
# ═════════════════════════════════════════════════════════════════════════════

try:
    from pymongo.errors import DuplicateKeyError  # type: ignore[reportMissingImports]
except ImportError:
    DuplicateKeyError = Exception  # type: ignore[misc,assignment]


def _get_mongodb_config(config: dict) -> tuple[str, str]:
    """Extract MongoDB URI and database name from pipeline config."""
    db_cfg = config.get("database", {})
    uri = db_cfg.get("mongodb_uri", "mongodb://localhost:27017/")
    db_name = db_cfg.get("mongodb_database", "western_armenian_corpus")
    return uri, db_name


@contextmanager
def open_mongodb_client(config: dict) -> Generator:
    """Context manager that yields a connected MongoDBCorpusClient.

    Falls back gracefully: yields None and logs an error if pymongo is
    missing or the connection fails.
    """
    try:
        from hytools.integrations.database.mongodb_client import MongoDBCorpusClient
    except ImportError:
        logger.error("pymongo not installed. Run: pip install pymongo")
        yield None
        return

    uri, db_name = _get_mongodb_config(config)
    client = MongoDBCorpusClient(uri=uri, database_name=db_name)
    try:
        client.connect()
        logger.info("Connected to MongoDB: %s", db_name)
        yield client
    except Exception as exc:
        logger.error("MongoDB connection failed: %s", exc)
        yield None
    finally:
        client.close()


def _compute_document_metrics(text: str, text_id: str, source: str) -> dict | None:
    """Compute TextMetricCard, loanword metadata, and per-document word counts.

    Used when database.compute_metrics_on_ingest is True.
    Stores document_metrics (lexical, syntactic, loanwords, possible_loanwords,
    word_counts). word_counts is a dict of word -> count for every token in the text.
    Returns None on failure (ingestion continues without metrics).
    """
    try:
        from collections import Counter

        from dataclasses import asdict

        from hytools.cleaning.armenian_tokenizer import extract_words
        from hytools.linguistics.metrics.text_metrics import QuantitativeLinguisticsAnalyzer
        from hytools.linguistics.loanword_tracker import (
            analyze_loanwords,
            analyze_possible_loanwords,
        )

        result: dict = {}

        # TextMetricCard (quantitative linguistics)
        analyzer = QuantitativeLinguisticsAnalyzer()
        card = analyzer.analyze_text(text, text_id=text_id, source=source)
        result.update(asdict(card))

        # Loanword report (counts by source language, unique words per text)
        lw_report = analyze_loanwords(text, text_id=text_id, source=source)
        result["loanwords"] = lw_report.to_dict()

        # Possible loanwords based on dictionary coverage (expert-review list).
        possible_report = analyze_possible_loanwords(text, text_id=text_id, source=source)
        result["possible_loanwords"] = possible_report.to_dict()

        # Per-document word count: every word in this text with its count.
        words = extract_words(text, min_length=1)
        result["word_counts"] = dict(Counter(words))

        return result
    except Exception as exc:
        logger.debug("Could not compute metrics for ingest: %s", exc)
        return None


def _check_drift_on_ingest(metrics: dict, metadata: dict, config: dict) -> dict | None:
    """Optionally run drift check on document metrics and return a summary for metadata.drift_check.

    When database.drift_check_on_ingest or scraping.drift_check_on_ingest is True,
    loads baseline (WA or EA from metadata.source_language_code), computes z-scores for key metrics,
    and returns a dict with anomalous flag and alerts when any metric exceeds threshold.
    Returns None if disabled, no baseline, or no anomaly.
    """
    if not (config.get("database", {}).get("drift_check_on_ingest", False)
            or config.get("scraping", {}).get("drift_check_on_ingest", False)):
        return None
    try:
        from pathlib import Path

        from hytools.augmentation.baseline_statistics import CorpusBaselineComputer

        dialect = (metadata or {}).get("source_language_code") or "hyw"
        baseline_path = ("cache/wa_metric_baseline_stats.json"
                        if dialect == "hyw" else "cache/ea_metric_baseline_stats.json")
        computer = CorpusBaselineComputer()
        baseline = computer.load_statistics(baseline_path)
        if baseline is None:
            return None

        ttr = None
        purity = None
        lex = metrics.get("lexical") or {}
        qual = metrics.get("quality_flags") or {}
        if isinstance(lex, dict):
            ttr = lex.get("ttr")
        if isinstance(qual, dict):
            purity = qual.get("dialect_purity_score")
        alerts = []
        threshold = float(config.get("database", {}).get("drift_z_threshold") or
                         config.get("scraping", {}).get("drift_z_threshold") or 2.0)

        if ttr is not None and baseline.lexical_ttr is not None:
            z = baseline.lexical_ttr.normalize(float(ttr))
            if abs(z) > threshold:
                alerts.append({"metric": "lexical_ttr", "z_score": round(z, 2), "value": ttr})
        if purity is not None and baseline.quality_dialect_purity is not None:
            z = baseline.quality_dialect_purity.normalize(float(purity))
            if abs(z) > threshold:
                alerts.append({"metric": "quality_dialect_purity", "z_score": round(z, 2), "value": purity})

        if not alerts:
            return None
        return {
            "anomalous": True,
            "threshold_sigma": threshold,
            "alerts": alerts,
        }
    except Exception as exc:
        logger.debug("Drift check on ingest failed: %s", exc)
        return None


def insert_or_skip(
    client,
    *,
    source: str,
    title: str,
    text: str,
    url: str | None = None,
    author: str | None = None,
    metadata: dict | None = None,
    config: dict | None = None,
) -> bool:
    """Insert a document, returning True on success, False on duplicate/error.

    When config has database.compute_metrics_on_ingest or scraping.compute_metrics_on_ingest
    True, computes TextMetricCard per document and stores in metadata.document_metrics.
    """
    meta = dict(metadata or {})
    compute_metrics = (
        (config or {}).get("database", {}).get("compute_metrics_on_ingest", False)
        or (config or {}).get("scraping", {}).get("compute_metrics_on_ingest", True)
    )
    if compute_metrics and text.strip():
        metrics = _compute_document_metrics(text, text_id=title[:100] or "doc", source=source)
        if metrics:
            meta["document_metrics"] = metrics
            drift_check = _check_drift_on_ingest(metrics, meta, config or {})
            if drift_check:
                meta["drift_check"] = drift_check

    try:
        client.insert_document(
            source=source, title=title, text=text,
            url=url, author=author, metadata=meta,
        )
        return True
    except DuplicateKeyError:
        return False
    except Exception as exc:
        logger.error("MongoDB insert error (%s / %s): %s", source, title[:60], exc)
        return False


# ═════════════════════════════════════════════════════════════════════════════
#  Western Armenian language classifier
# ═════════════════════════════════════════════════════════════════════════════

_CLASSICAL_ORTHO_MARKERS: list[tuple[str, float]] = [
    ("\u0565\u0561", 2.0),       # եա ea diphthong (WA retains, EA reformed to ya)
    ("\u056B\u0582", 3.0),       # իւ iv → yu/yoo (classical spelling)
    ("\u0574\u0567\u057B", 2.5), # մէջ mech "in/among" (WA: ջ=ch; classical long է)
    ("\u056B\u0582\u0580\u0561\u0584\u0561\u0576\u0579\u056B\u0582\u0580", 4.0),  # իւրաքանչիւր yurakanchoor "each"
    ("\u056C\u0565\u0566\u0578\u0582", 1.5),  # լեզու lezoo "language"
    ("\u0578\u0575", 2.0),       # ոյ oy diphthong (classical)
    ("\u0561\u0575", 2.0),      # այ ay diphthong (classical)
]

_LEXICAL_MARKERS: list[tuple[str, float]] = [
    # NOTE: Short markers (al, gu, hon, hos, il) moved to _WA_STANDALONE_RE /
    # _WA_SUFFIX_RE below for word-boundary safety.
    ("\u056F\u055A", 2.0),           # կ՚ g' (elided before vowel)
    ("\u056F\u0578\u0580", 2.0),     # կոր gor (WA present progressive)
    ("\u057A\u056B\u057F\u056B", 2.0),   # պիտի bidi (WA future marker)
    ("\u0570\u056B\u0574\u0561", 2.0),   # հիմա hima (WA "now")
    ("\u0578\u0579\u056B\u0576\u0579", 2.5),    # ոչինչ vochinch (WA "nothing")
    ("\u0562\u0561\u0576 \u0574\u0568", 2.0),   # բան մը pan mu (WA "something")
    ("\u0579\u0565\u0574", 2.0),     # չեմ chem (WA negative particle)
    ("\u0574\u0565\u0576\u0584", 2.0),   # մենք menk (WA "we")
    ("\u0563\u0565\u0572\u0565\u0581\u056B\u056F", 1.5),  # գեղեցիկ keghetsig (WA "beautiful")
]

_WA_VOCABULARY: list[tuple[str, float]] = [
    ("\u0573\u0565\u0580\u0574\u0561\u056f", 3.0),   # ճերմակ jermag (WA "white")
    ("\u056d\u0578\u0570\u0561\u0576\u0578\u0581", 3.0),  # խոհանոց khohanots (WA "kitchen")
    ("\u057B\u0578\u0582\u0580", 2.5),   # ջուր choor (WA "water"; ջ=ch)
    ("\u0577\u0561\u057a\u056b\u056f", 3.0),  # շապիկ shabig (WA "shirt")
    ("\u0574\u0561\u0576\u0578\u0582\u056f", 3.0),  # մանուկ manoog (WA "child"; կ=g)
    ("\u057f\u0572\u0561\u0575", 2.5),     # տղայ dgha (WA "boy"; silent յ)
    ("\u056d\u0585\u057d\u056b\u056c", 2.5),  # խօսիլ khosil (WA "to speak")
    ("\u0565\u0580\u0569\u0561\u056c", 2.5),  # երթալ yertal (WA "to go"; թ=t)
    ("\u0568\u0576\u0565\u056c", 2.5),   # ընել unel (WA "to do"; ը=u)
    ("\u0578\u0582\u0566\u0565\u056c", 2.5),  # ուզել oozel (WA "to want")
    ("\u0570\u0561\u057d\u056f\u0576\u0561\u056c", 2.5),  # հասկնալ hasgnal (WA "to understand")
    ("\u0561\u0580\u0564\u0567\u0576", 2.5),  # արդէն arten (WA "already"; դ=t, է=e)
    ("\u0570\u0561\u057a\u0561", 2.5),   # հապա haba (WA "then/so")
    ("\u0577\u0561\u057f", 2.5),     # շատ shad (WA "very/much")
    ("\u056f\u056b\u0580\u0561\u056f\u056b", 2.5),  # կիրակի giragi (WA "Sunday"; կ=g)
    ("\u0570\u0561\u057e\u056f\u056b\u0569", 2.5),  # հաւկիթ havgit (WA "egg"; EA uses ձու)
    ("\u057e\u0561\u0580\u057f\u056b\u0569", 2.5),  # վարտիք vardig (WA "underwear"; տ=d; EA false friend վարդիկ "little rose")
]

_EASTERN_ARMENIAN_REFORM_MARKERS: list[tuple[str, float]] = [
    ("\u0574\u056B\u0575", 2.0),  # միյ miy (EA reformed digraph; WA uses classical)
    ("\u056D\u0576\u0561\u0575\u0574", 2.0),  # խնայմ khnaym (EA reformed)
    ("\u0568\u0575\u056E\u0561\u056C", 2.0),  # թյուն tyoon (EA reformed)
    ("\u0568\u0561\u0576", 2.0) #at the end of a person last name, in western armenian this would be եան instead of յան
]

# EA indefinite article: մի (mi) BEFORE noun — subtract from WA score (WA uses մը mu)
_EASTERN_INDEFINITE_ARTICLE: list[tuple[str, float]] = [
    ("\u0574\u056B ", 2.5),  # մի + space noun (EA "մի"; WA uses մը)
]

# EA vocabulary: terms typical of Eastern Armenian (subtract from WA score)
_EASTERN_VOCABULARY: list[tuple[str, float]] = [
    ("\u0571\u0578\u0582", 2.5),  # ձու tsoo (EA "egg"; WA ձ=ts; WA uses հաւկիթ havgit)
]

# == Word-boundary-aware WA markers ============================================
# Short markers (2-3 Armenian chars) cause false positives with substring
# matching (e.g. 'ալ' matching inside longer Eastern Armenian words).
# These use regex with Armenian word boundaries for accurate counting.
#
# Armenian word boundary = not preceded/followed by Armenian letter (U+0531-U+0586).
# Range ends at ֆ (U+0586), excluding և (U+0587) which is only the conjunction "and".
_ARM_WB_L = r'(?<![Ա-ֆ])'   # left word boundary (standalone start)
_ARM_WB_R = r'(?![Ա-ֆ])'    # right word boundary (standalone end)
_ARM_PRECEDED = r'(?<=[Ա-ֆ])'  # must follow an Armenian letter (suffix)

# Standalone WA words (boundary on BOTH sides)
_WA_STANDALONE_RE: list[tuple[re.Pattern, float]] = [
    # ալ (al) = "also/too".  2 chars — collides inside EA words.
    (re.compile(_ARM_WB_L + r'\u0561\u056C' + _ARM_WB_R), 1.0),
    # կը (gu) = present-tense prefix.  2 chars.
    (re.compile(_ARM_WB_L + r'\u056F\u0568' + _ARM_WB_R), 2.0),
    # հոն (hon) = "there".  3 chars.
    (re.compile(_ARM_WB_L + r'\u0570\u0578\u0576' + _ARM_WB_R), 3.0),
    # հոս (hos) = "here".  3 chars.
    (re.compile(_ARM_WB_L + r'\u0570\u0578\u057D' + _ARM_WB_R), 3.0),
]

# WA suffixes (boundary on RIGHT side only — preceded by Armenian letter)
_WA_SUFFIX_RE: list[tuple[re.Pattern, float]] = [
    # -իլ (-il) = infinitive suffix.  2 chars — collides as substring.
    (re.compile(_ARM_PRECEDED + r'\u056B\u056C' + _ARM_WB_R), 1.5),
]

# == EA regex-based markers (suffix/prefix patterns with word boundaries) ======
# These detect EA-specific morphological patterns that need proper boundaries.
_EA_REGEX_MARKERS: list[tuple[re.Pattern, float]] = [
    # -ում (-um) = EA present-tense / imperfective suffix.  THE #1 EA signal.
    # EA: "verb-oom yem" (I verb).  WA never uses this construction.
    (re.compile(_ARM_PRECEDED + r'\u0578\u0582\u0574' + _ARM_WB_R), 2.5),
    # և (U+0587) INSIDE a word = EA reformed spelling.  In WA, և is ONLY the
    # standalone conjunction "and" (yev); it never appears inside words.
    # EA reform merged classical digraph եdelays into the ligature և within words.
    (re.compile(r'[\u0531-\u0586]\u0587[\u0531-\u0586]'), 3.0),
]

# Known WA authors (diaspora literary figures) — boost WA score
_WA_AUTHORS: list[tuple[str, float]] = [
    # Classical / foundational
    ("\u0544\u0565\u056D\u056B\u0569\u0561\u0580", 5.0),       # Մեխիթար Mekhitar (Mekhitarists)
    ("\u0544\u056D\u056B\u0569\u0561\u0580\u0565\u0561\u0576", 5.0),  # Մխիթարեան Mekhitarean

    # 19th-20th century WA literary figures
    ("\u054F\u0561\u0576\u056B\u0567\u056C", 4.0),             # Տանիէլ Taniel (Varoujan)
    ("\u054E\u0561\u0580\u0578\u0582\u056A\u0561\u0576", 5.0), # Վարուժան Varoujan
    ("\u054D\u056B\u0561\u0574\u0561\u0576\u0569\u0578", 5.0), # Սիամանթո Siamanto
    ("\u0536\u0561\u0580\u056B\u0586\u0565\u0561\u0576", 4.0), # Զարիֆեան Zarifean
    ("\u054F\u0565\u0584\u0567\u0565\u0561\u0576", 5.0),       # Տեքէեան Tekeyan
    ("\u0546\u056B\u056F\u0578\u0572\u0578\u057D", 4.0),       # Նիկողոս Nikoghos (Sarafian etc.)
    ("\u054D\u0561\u0580\u0561\u0586\u0565\u0561\u0576", 5.0), # Սարաֆեան Sarafian
    ("\u0547\u0561\u0570\u0561\u0576", 3.0),                   # Շահան Shahan (Shahnour etc.)
    ("\u0547\u0561\u0570\u0576\u0578\u0582\u0580", 5.0),       # Շահնուր Shahnour
    ("\u0546\u056B\u056F\u0578\u0572\u0561\u0575\u0578\u057D", 4.0),  # Նիկողայոս Nikoghayos
    ("\u0531\u0563\u0578\u0576\u0581", 3.0),                   # Ագոնց Agonts
    ("\u0536\u0561\u0580\u0564\u0561\u0580\u0565\u0561\u0576", 5.0),  # Զարդարեան Zardarian
    ("\u0555\u0577\u0561\u056F\u0561\u0576", 5.0),             # Օշական Oshakan
    ("\u0536\u0561\u057A\u0567\u056C", 4.0),                   # Զապէլ Zabel (Yesayan)
    ("\u0535\u057D\u0561\u0575\u0565\u0561\u0576", 5.0),       # Եսայեան Yesayan
    ("\u0540\u0561\u0574\u0561\u057D\u057F\u0565\u0572", 4.0), # Համաստեղ Hamastegh
    ("\u0546\u0578\u0580\u0561\u0575\u0580", 4.0),             # Նորայր Norayr
    ("\u054A\u0565\u0577\u056B\u056F\u0569\u0561\u0577\u056C\u0565\u0561\u0576", 5.0),  # Պեշիկթաշլեան Beshiktashlean
    ("\u054A\u0565\u0577\u056B\u056F\u0569\u0561\u0577\u056C\u056B\u0561\u0576", 5.0),  # Պեշիկթաշլիան Beshiktashlian (alternate)
    ("\u054E\u0561\u0580\u0564\u0561\u0576\u0565\u0561\u0576", 4.0),  # Վարդանեան Vardanean
    ("\u0531\u056C\u056B\u0577\u0561\u0576", 4.0),              # Ալիշան Alishan
    ("\u0539\u0578\u0583\u0579\u0565\u0561\u0576", 4.0),        # Թոփչեան Topchean
    ("\u0536\u0578\u0570\u0580\u0561\u057A", 5.0),              # Զոհրապ Zohrap
    ("\u0544\u056B\u057D\u0561\u0584\u0565\u0561\u0576", 4.0),  # Միսաքեան Misakean
    ("\u054A\u0561\u0580\u0578\u0576\u0565\u0561\u0576", 4.0),  # Պարոնեան Baronean
]

# Known WA publication cities (diaspora centres)
_WA_PUBLICATION_CITIES: list[tuple[str, float]] = [
    ("\u054A\u0567\u0575\u0580\u0578\u0582\u0569", 4.0),       # Պէյրութ Peyrouth (Beirut)
    ("\u054A\u0578\u056C\u056B\u057D", 3.0),                   # Պոլիս Bolis (Istanbul in WA)
    ("\u0553\u0561\u0580\u056B\u0566", 3.5),                   # Փարիզ Bariz (Paris)
    ("\u0543\u0561\u0570\u056B\u0580\u0567", 3.5),             # Ճահիրէ Gahireh (Cairo)
    ("\u054A\u0578\u057D\u0569\u0578\u0576", 3.0),             # Պոսթոն Posdon (Boston)
    ("\u0546\u056B\u0582 \u0535\u0578\u0580\u0584", 3.5),      # Նիւ Եորք Niw York (New York)
    ("\u053E\u0578\u0582\u0580\u056B\u056D", 3.0),             # Ծուրիխ Tsurikh (Zurich)
    ("\u053E\u0565\u0576\u0567\u0582", 3.0),                   # Ծենէւ Tsenev (Geneva)
    ("\u054E\u056B\u0567\u0576\u0576\u0561", 3.0),             # Վիէննա Vienna
    ("\u054D\u0561\u0576 \u053C\u0561\u0566\u0561\u0580\u0578", 3.0),  # Սան Լազարո San Lazaro
    ("\u054E\u0565\u0576\u0565\u057F\u056B\u056F", 3.5),       # Վենետիկ Venedig (Venice)
    ("\u0540\u0561\u056C\u0567\u057A", 4.0),                   # Հալէպ Halep (Aleppo)
    ("\u0531\u0576\u0569\u056B\u056C\u056B\u0561\u057D", 3.0), # Անթիլիաս Antilias
    ("\u053F\u056B\u056C\u056B\u056F\u056B\u0561", 3.0),       # Կիլիկիա Cilicia
    ("\u0544\u0561\u0580\u057D\u0567\u0575", 3.0),             # Մարսէյ Marseille
    ("\u0544\u0578\u0576\u0569\u0580\u0567\u0561\u056C", 3.0), # Մոնթրէալ Montreal
    ("\u053F\u0561\u0570\u056B\u0580\u0567", 3.5),             # Կահիրէ Gahireh (Cairo alt spelling)
    ("\u0532\u0578\u0582\u0565\u0576\u0578\u057D \u0531\u0575\u0580\u0567\u057D", 3.5),  # Բուենոս Այրէս Buenos Aires
    ("\u054D\u0561\u0576 \u054A\u0561\u0578\u0582\u056C\u0578", 3.0),  # Սան Պաուլո San Paulo
]

# Armenian letter է (e long) between two Armenian letters — classical WA
_WORD_INTERNAL_E_LONG_RE = re.compile(r"[\u0531-\u0586]\u0567[\u0531-\u0586]")
# Word-ending այ (ay) — classical diphthong; very indicative of traditional spelling
_WORD_ENDING_AY_RE = re.compile(r"\u0561\u0575(?=[\s\u0589\u055D\u055E,.;:!?]|\Z)")
# Word-ending ոյ (oy) — classical diphthong; very indicative of traditional spelling
_WORD_ENDING_OY_RE = re.compile(r"\u0578\u0575(?=[\s\u0589\u055D\u055E,.;:!?]|\Z)")
# Word-ending յ (y) — traditional spelling; reformed often drops final յ
_WORD_ENDING_Y_RE = re.compile(r"\u0575(?=[\s\u0589\u055D\u055E,.;:!?]|\Z)")

WA_SCORE_THRESHOLD = 5.0


def _has_armenian_script(text: str, threshold: float = 0.2) -> bool:
    """Return True if at least *threshold* fraction of characters are Armenian."""
    if not text:
        return False
    armenian = sum(1 for c in text if "\u0530" <= c <= "\u058F")
    return armenian / len(text) >= threshold


def _any_armenian_script(text: str) -> bool:
    """Return True if *text* contains at least one Armenian script character (U+0530–U+058F).

    Use this instead of ``_has_armenian_script`` when you want to apply a
    computation to *any* document that touches Armenian script, regardless of
    what fraction of the text is Armenian.
    """
    return any("\u0530" <= c <= "\u058F" for c in text)


def compute_script_purity_score(text: str) -> float:
    """Return the fraction of characters that are Armenian script (U+0530–U+058F).

    1.0 = fully Armenian, 0.0 = no Armenian.  Values below ~0.5 on a document
    that should be Armenian typically indicate OCR contamination (Latin or other
    characters mixed in).  Cheap to compute; useful for post-OCR quality gating.
    """
    if not text:
        return 0.0
    armenian = sum(1 for c in text if "\u0530" <= c <= "\u058F")
    return armenian / len(text)


def compute_wa_score_detailed(text: str) -> dict:
    """Compute a detailed Western Armenian score breakdown for *text*.

    Returns a dict with per-component scores and the total.  Positive
    components represent WA evidence; ``ea_penalty`` is the negative
    EA-signal subtraction stored as a negative float.

    Keys
    ----
    total             Final weighted sum. Same value as compute_wa_score().
    classical_ortho   Classical orthographic markers: եա/իւ digraphs,
                      word-internal long-ē (է), final diphthongs -այ/-ոյ/-յ.
    lexical_grammar   Grammatical particles and fixed WA words (կը, պիտի,
                      մը, ալ, հոն, հոս, -իլ suffix, etc.) with
                      word-boundary-safe regex matching.
    vocabulary        WA-specific vocabulary (ճերմակ, ջուր, շапիկ, etc.)
    ea_penalty        Eastern Armenian signals: reform markers, մի article,
                      ձու vocab, -ում suffix, և-inside-word. Stored as a
                      negative float (amount subtracted from total).
    provenance_bonus  Known WA author names or diaspora publication cities
                      found in the text.
    """
    if not text:
        return {
            "total": 0.0,
            "classical_ortho": 0.0,
            "lexical_grammar": 0.0,
            "vocabulary": 0.0,
            "ea_penalty": 0.0,
            "provenance_bonus": 0.0,
        }

    classical_ortho = 0.0
    lexical_grammar = 0.0
    vocabulary = 0.0
    ea_penalty = 0.0
    provenance_bonus = 0.0

    # 1. Classical orthographic markers (POSITIVE: WA signal)
    for marker, weight in _CLASSICAL_ORTHO_MARKERS:
        count = text.count(marker)
        if count:
            classical_ortho += weight * min(count, 10)

    # 2. Lexical / grammatical markers (POSITIVE: WA signal)
    for marker, weight in _LEXICAL_MARKERS:
        count = text.count(marker)
        if count:
            lexical_grammar += weight * min(count, 10)

    # 2a-i. WA standalone words via regex (word-boundary-safe)
    for pattern, weight in _WA_STANDALONE_RE:
        hits = len(pattern.findall(text))
        if hits:
            lexical_grammar += weight * min(hits, 10)

    # 2a-ii. WA suffixes via regex (word-boundary-safe)
    for pattern, weight in _WA_SUFFIX_RE:
        hits = len(pattern.findall(text))
        if hits:
            lexical_grammar += weight * min(hits, 10)

    # 2b. WA-specific vocabulary (POSITIVE: WA signal)
    for marker, weight in _WA_VOCABULARY:
        count = text.count(marker)
        if count:
            vocabulary += weight * min(count, 10)

    # 2c. Eastern Armenian reform markers (NEGATIVE: EA signal)
    for marker, weight in _EASTERN_ARMENIAN_REFORM_MARKERS:
        count = text.count(marker)
        if count:
            ea_penalty -= weight * min(count, 10)

    # 2d. Eastern Armenian indefinite article (NEGATIVE: EA signal)
    for marker, weight in _EASTERN_INDEFINITE_ARTICLE:
        count = text.count(marker)
        if count:
            ea_penalty -= weight * min(count, 10)

    # 2e. Eastern Armenian vocabulary (NEGATIVE: EA signal)
    for marker, weight in _EASTERN_VOCABULARY:
        count = text.count(marker)
        if count:
            ea_penalty -= weight * min(count, 10)

    # 2f. EA regex-based markers (NEGATIVE: EA signal)
    for pattern, weight in _EA_REGEX_MARKERS:
        hits = len(pattern.findall(text))
        if hits:
            ea_penalty -= weight * min(hits, 10)

    # 3. Word-internal long-e (POSITIVE: classical orthography = WA signal)
    internal_hits = len(_WORD_INTERNAL_E_LONG_RE.findall(text))
    if internal_hits:
        classical_ortho += 1.0 * min(internal_hits, 20)

    # 3b. Word-final diphthongs -ay and -oy (POSITIVE: classical orthography)
    ay_hits = len(_WORD_ENDING_AY_RE.findall(text))
    oy_hits = len(_WORD_ENDING_OY_RE.findall(text))
    y_end_hits = len(_WORD_ENDING_Y_RE.findall(text))
    if ay_hits:
        classical_ortho += 1.5 * min(ay_hits, 15)
    if oy_hits:
        classical_ortho += 2.0 * min(oy_hits, 15)
    if y_end_hits:
        classical_ortho += 1.5 * min(y_end_hits, 15)

    # 4. Author names (WA authors boost score)
    for name, weight in _WA_AUTHORS:
        if name in text:
            provenance_bonus += weight

    # 5. Publication cities
    for city, weight in _WA_PUBLICATION_CITIES:
        if city in text:
            provenance_bonus += weight

    total = classical_ortho + lexical_grammar + vocabulary + ea_penalty + provenance_bonus

    return {
        "total": round(total, 3),
        "classical_ortho": round(classical_ortho, 3),
        "lexical_grammar": round(lexical_grammar, 3),
        "vocabulary": round(vocabulary, 3),
        "ea_penalty": round(ea_penalty, 3),
        "provenance_bonus": round(provenance_bonus, 3),
    }


def compute_wa_score(text: str) -> float:
    """Compute a weighted Western Armenian score for *text*.

    Returns the total score only. For per-component breakdown use
    ``compute_wa_score_detailed()``.  Higher score = stronger WA signal.
    Threshold for Western Armenian classification: WA_SCORE_THRESHOLD (5.0).
    """
    return compute_wa_score_detailed(text)["total"]


def is_armenian(text: str) -> bool:
    """Return True if *text* is primarily Armenian (Eastern or Western)."""
    return _has_armenian_script(text)


def is_western_armenian(text: str, threshold: float | None = None) -> bool:
    """Determine if *text* is Western Armenian using multi-signal scoring."""
    if not _has_armenian_script(text):
        return False
    thresh = threshold if threshold is not None else WA_SCORE_THRESHOLD
    return compute_wa_score(text) >= thresh


def try_wa_filter(text: str) -> bool | None:
    """Classify *text* as WA (True), not-WA (False), or unknown (None).

    Returns None only if the text has no Armenian script (and thus the
    classifier cannot make a determination).
    """
    if not _has_armenian_script(text):
        return None
    return is_western_armenian(text)


def classify_language(text: str) -> tuple[str, str]:
    """Derive internal language code and branch from text analysis.

    Returns
    -------
    (internal_language_code, internal_language_branch):
        - ``("hy", "hye-w")`` — Western Armenian
        - ``("hy", "hye-e")`` — Eastern Armenian (or Armenian below WA threshold)
        - ``("eng", "eng")``  — English (no Armenian script detected)
    """
    if _has_armenian_script(text):
        if compute_wa_score(text) >= WA_SCORE_THRESHOLD:
            return ("hy", "hye-w")
        return ("hy", "hye-e")
    return ("eng", "eng")


# ═════════════════════════════════════════════════════════════════════════════
#  Wikitext processing
# ═════════════════════════════════════════════════════════════════════════════

_DUMP_BASE = "https://dumps.wikimedia.org/{lang}wiki/{date}/"
_ARTICLES_DUMP = "{lang}wiki-{date}-pages-articles.xml.bz2"

_RE_TEMPLATE = re.compile(r"\{\{[^}]*\}\}")
# Պատկ Patk/Badg = "image" (WA: պ=b, so Badg)
_RE_FILE_LINK = re.compile(r"\[\[(File|Image|\u054a\u0561\u057f\u056f):.*?\]\]", re.IGNORECASE)
_RE_CATEGORY = re.compile(r"\[\[Category:.*?\]\]", re.IGNORECASE)
_RE_EXT_LINK = re.compile(r"\[https?://[^\]]*\]")
_RE_REF = re.compile(r"<ref[^>]*>.*?</ref>|<ref[^/]*/?>", re.DOTALL)
_RE_HTML_TAG = re.compile(r"<[^>]+>")
_RE_HEADING = re.compile(r"={2,6}\s*(.*?)\s*={2,6}")
_RE_BOLD_ITALIC = re.compile(r"'{2,5}")
_RE_LIST_MARKER = re.compile(r"^[*#:;]+\s*", re.MULTILINE)
_RE_TABLE = re.compile(r"\{\|.*?\|\}", re.DOTALL)
_RE_INTERNAL_LINK = re.compile(r"\[\[([^|\]]*\|)?([^\]]+)\]\]")
_RE_REDIRECT = re.compile(r"^#REDIRECT", re.IGNORECASE)


def clean_wikitext(raw: str) -> str:
    """Strip wikitext markup from *raw* and return plain text."""
    text = raw
    text = _RE_TEMPLATE.sub("", text)
    text = _RE_TABLE.sub("", text)
    text = _RE_FILE_LINK.sub("", text)
    text = _RE_CATEGORY.sub("", text)
    text = _RE_REF.sub("", text)
    text = _RE_HTML_TAG.sub("", text)
    text = _RE_EXT_LINK.sub("", text)
    text = _RE_HEADING.sub(r"\1", text)
    text = _RE_BOLD_ITALIC.sub("", text)
    text = _RE_LIST_MARKER.sub("", text)
    text = _RE_INTERNAL_LINK.sub(r"\2", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_redirect(raw: str) -> bool:
    """Return True if *raw* wikitext is a redirect page."""
    return bool(_RE_REDIRECT.match(raw))


def resolve_dump_date(lang: str, requested: str) -> str:
    """Return the latest available dump date if *requested* is ``'latest'``."""
    if requested != "latest":
        return requested
    url = _DUMP_BASE.format(lang=lang, date="latest") + "dumpstatus.json"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("version", "latest")
    except Exception:
        logger.warning("Could not resolve latest dump date for %s; using 'latest'", lang)
        return "latest"


def download_dump(lang: str, date: str, dest_dir: Path) -> Path:
    """Download a Wikipedia articles XML dump and return its local path."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = _ARTICLES_DUMP.format(lang=lang, date=date)
    url = _DUMP_BASE.format(lang=lang, date=date) + filename
    dest = dest_dir / filename

    if dest.exists():
        logger.info("Dump already downloaded: %s", dest)
        return dest

    logger.info("Downloading Wikipedia dump from %s", url)
    with requests.get(url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
    logger.info("Download complete: %s (%d bytes)", dest, dest.stat().st_size)
    return dest


# ═════════════════════════════════════════════════════════════════════════════
#  Newspaper issue splitter (for archive_org and other full-issue OCR blobs)
# ═════════════════════════════════════════════════════════════════════════════

_RE_DATE = re.compile(
    r"(19[0-9]{2}|20[0-9]{2})"  # simple year match 1900–2099
)

_SECTION_KEYWORDS = (
    "\u0533\u053C\u0552\u054E\u053D",  # ԳԼՈՒԽ
    "\u0532\u0531\u056E\u056B\u0576",  # ԲԱԺԻՆ
    "\u053D\u0544\u0532\u0531\u0533\u056B\u0580",  # ԽՄԲԱԳԻՐ
    "\u053D\u0544\u0532\u0531\u0533\u0580\u0531\u053F\u0531\u053F",  # ԽՄԲԱԳՐԱԿԱՆ
    "\u0540\u0552\u0534\u054E\u0531\u056F\u054F",  # ՀՕԴՎԱԾ
)


@dataclass
class ArticleChunk:
    """Single article (or sub-article chunk) extracted from an issue."""

    text: str
    title: str | None
    article_index: int


def _is_probable_header(line: str) -> bool:
    """Heuristic: is this line likely an article header/title?"""
    stripped = line.strip()
    if not stripped:
        return False

    letters = [ch for ch in stripped if "\u0530" <= ch <= "\u058F"]
    if not letters:
        return False

    upper = sum(1 for ch in letters if ch == ch.upper())
    if letters and upper / len(letters) >= 0.7:
        return True

    if _RE_DATE.search(stripped):
        return True
    for kw in _SECTION_KEYWORDS:
        if kw in stripped:
            return True

    return False


def _byte_len(s: str) -> int:
    return len(s.encode("utf-8"))


def split_issue_into_articles(
    text: str,
    max_bytes: int = 12_000_000,
) -> List[ArticleChunk]:
    """Split a full-issue OCR blob into article-like chunks.

    Uses heuristics (header-like lines, dates, section keywords) to find split
    points. Optionally, callers can use the **news_article_catalog** (MongoDB)
    to supply known article titles/URLs for the same publication to improve
    segment boundaries and titles; see ingestion.acquisition.news and
    FUTURE_IMPROVEMENTS.md.

    Parameters
    ----------
    text:
        Full OCR text for the issue (after any global cleanup step).
    max_bytes:
        Soft cap for each article's encoded size. If an article exceeds this
        limit, it is split on paragraph boundaries into multiple chunks.

    Returns
    -------
    list[ArticleChunk]
        Ordered list of ArticleChunk instances (text, title, article_index).
    """
    lines = text.splitlines()

    candidate_indices: list[int] = []
    for i, line in enumerate(lines):
        if _is_probable_header(line):
            prev_blank = i > 0 and not lines[i - 1].strip()
            next_blank = i + 1 < len(lines) and not lines[i + 1].strip()
            if prev_blank or next_blank:
                candidate_indices.append(i)

    if not candidate_indices:
        return _split_large_article(
            ArticleChunk(text=text.strip(), title=None, article_index=0),
            max_bytes=max_bytes,
        )

    articles: List[ArticleChunk] = []
    indices = candidate_indices + [len(lines)]

    for idx, (start, end) in enumerate(zip(indices, indices[1:])):
        seg_lines = lines[start:end]
        segment_text = "\n".join(seg_lines).strip()
        if not segment_text:
            continue

        title = seg_lines[0].strip() if seg_lines else None
        base_chunk = ArticleChunk(text=segment_text, title=title, article_index=idx)
        chunks = _split_large_article(base_chunk, max_bytes=max_bytes)
        articles.extend(chunks)

    return articles


def _split_large_article(article: ArticleChunk, max_bytes: int) -> List[ArticleChunk]:
    """Ensure a single article respects the max_bytes cap by sub-splitting."""
    if _byte_len(article.text) <= max_bytes:
        return [article]

    paragraphs = [p for p in article.text.split("\n\n") if p.strip()]
    chunks: List[ArticleChunk] = []
    buf: list[str] = []
    buf_bytes = 0
    sub_index = 0

    for para in paragraphs:
        para_text = para.strip()
        if not para_text:
            continue
        para_bytes = _byte_len(para_text + "\n\n")

        if buf and buf_bytes + para_bytes > max_bytes:
            chunk_text = ("\n\n".join(buf)).strip()
            chunks.append(
                ArticleChunk(
                    text=chunk_text,
                    title=article.title,
                    article_index=article.article_index * 1000 + sub_index,
                )
            )
            buf = []
            buf_bytes = 0
            sub_index += 1

        buf.append(para_text)
        buf_bytes += para_bytes

    if buf:
        chunk_text = ("\n\n".join(buf)).strip()
        chunks.append(
            ArticleChunk(
                text=chunk_text,
                title=article.title,
                article_index=article.article_index * 1000 + sub_index,
            )
        )

    return chunks


# ═════════════════════════════════════════════════════════════════════════════
#  Catalog I/O (MongoDB only — no JSON/txt persistence)
# ═════════════════════════════════════════════════════════════════════════════

def load_catalog_from_mongodb(client, source: str) -> dict[str, dict]:
    """Load catalog from MongoDB. Returns empty dict if client is None or no items."""
    if client is None:
        return {}
    return client.get_catalog(source)


def save_catalog_to_mongodb(client, source: str, catalog: dict[str, dict]) -> int:
    """Upsert catalog items to MongoDB. Returns count upserted."""
    if client is None:
        return 0
    return client.upsert_catalog_items(source, catalog)


def log_stage(logger_instance: logging.Logger, stage: str, action: str, **kwargs) -> None:
    """Log a stage-level event with structured context for triage."""
    extra = " ".join(f"{k}={v!r}" for k, v in sorted(kwargs.items()) if v is not None)
    msg = f"[{stage}] {action}"
    if extra:
        msg += f" | {extra}"
    logger_instance.info(msg)


def log_item(
    logger_instance: logging.Logger,
    level: str,
    stage: str,
    item_id: str,
    action: str,
    status: str | None = None,
    duration_ms: float | None = None,
    error: str | None = None,
    **kwargs,
) -> None:
    """Log an item-level event with structured context for triage."""
    parts = [f"[{stage}]", f"item_id={item_id!r}", f"action={action!r}"]
    if status:
        parts.append(f"status={status!r}")
    if duration_ms is not None:
        parts.append(f"duration_ms={duration_ms:.0f}")
    if error:
        parts.append(f"error={error!r}")
    for k, v in sorted(kwargs.items()):
        if v is not None:
            parts.append(f"{k}={v!r}")
    getattr(logger_instance, level)(" | ".join(parts))
