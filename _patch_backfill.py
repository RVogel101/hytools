"""
One-shot patch: replace the buggy backfill else-block in metadata_tagger.py
with the clean restructured version that:
  - fixes the _has_armenian_script NameError latent bug
  - switches to _any_armenian_script threshold-free check
  - adds text_metrics + loanwords backfill with text_metrics_date sentinel
"""
import pathlib, sys

TARGET = pathlib.Path(__file__).with_name("ingestion") / "enrichment" / "metadata_tagger.py"

# The existing (mojibake comment) text — using raw bytes avoids encoding fights
OLD = (
    "            else:\n"
    "                # Already enriched \u00e2\u20ac\u201d still backfill internal language classification\n"
    "                # and stats if missing.\n"
    "                if text.strip() and existing.get(\"internal_language_branch\") is None:\n"
    "                    from ingestion._shared.helpers import classify_language, compute_wa_score_detailed, _has_armenian_script\n"
    "\n"
    "                    lang_code, lang_branch = classify_language(text)\n"
    "                    stats_update[\"metadata.internal_language_code\"] = lang_code\n"
    "                    stats_update[\"metadata.internal_language_branch\"] = lang_branch\n"
    "                if text.strip() and existing.get(\"wa_score\") is None and _has_armenian_script(text):\n"
    "                    from ingestion._shared.helpers import compute_wa_score_detailed, _has_armenian_script\n"
    "\n"
    "                    stats_update[\"metadata.wa_score\"] = compute_wa_score_detailed(text)\n"
    "                if text.strip() and existing.get(\"script_purity_score\") is None:\n"
    "                    from ingestion._shared.helpers import compute_script_purity_score\n"
    "\n"
    "                    stats_update[\"metadata.script_purity_score\"] = compute_script_purity_score(text)\n"
    "                if stats_update:"
)

NEW = (
    "            else:\n"
    "                # Already enriched \u2014 backfill any missing computed fields.\n"
    "                if text.strip():\n"
    "                    from ingestion._shared.helpers import (\n"
    "                        classify_language,\n"
    "                        compute_wa_score_detailed,\n"
    "                        compute_script_purity_score,\n"
    "                        _any_armenian_script,\n"
    "                    )\n"
    "\n"
    "                    _has_arm = _any_armenian_script(text)\n"
    "\n"
    "                    if existing.get(\"internal_language_branch\") is None:\n"
    "                        lang_code, lang_branch = classify_language(text)\n"
    "                        stats_update[\"metadata.internal_language_code\"] = lang_code\n"
    "                        stats_update[\"metadata.internal_language_branch\"] = lang_branch\n"
    "\n"
    "                    if existing.get(\"wa_score\") is None and _has_arm:\n"
    "                        stats_update[\"metadata.wa_score\"] = compute_wa_score_detailed(text)\n"
    "\n"
    "                    if existing.get(\"script_purity_score\") is None:\n"
    "                        stats_update[\"metadata.script_purity_score\"] = compute_script_purity_score(text)\n"
    "\n"
    "                    if existing.get(\"text_metrics_date\") is None and _has_arm:\n"
    "                        try:\n"
    "                            from dataclasses import asdict as _asdict\n"
    "                            from linguistics.metrics.text_metrics import QuantitativeLinguisticsAnalyzer\n"
    "                            from linguistics.lexicon.loanword_tracker import analyze_loanwords\n"
    "\n"
    "                            _card = QuantitativeLinguisticsAnalyzer().analyze_text(\n"
    "                                text, text_id=str(doc.get(\"_id\", \"\")), source=source\n"
    "                            )\n"
    "                            stats_update[\"metadata.text_metrics\"] = {\n"
    "                                \"lexical\": _asdict(_card.lexical),\n"
    "                                \"syntactic\": _asdict(_card.syntactic),\n"
    "                                \"morphological\": _asdict(_card.morphological),\n"
    "                                \"orthographic\": _asdict(_card.orthographic),\n"
    "                                \"semantic\": _asdict(_card.semantic),\n"
    "                                \"contamination\": _asdict(_card.contamination),\n"
    "                                \"quality_flags\": _asdict(_card.quality_flags),\n"
    "                            }\n"
    "                            stats_update[\"metadata.loanwords\"] = analyze_loanwords(\n"
    "                                text, text_id=str(doc.get(\"_id\", \"\")), source=source\n"
    "                            ).to_dict()\n"
    "                            stats_update[\"metadata.text_metrics_date\"] = datetime.now(timezone.utc).isoformat()\n"
    "                        except Exception as _tm_exc:\n"
    "                            logger.debug(\"text_metrics backfill failed for doc %s: %s\", doc.get(\"_id\"), _tm_exc)\n"
    "\n"
    "                if stats_update:"
)

content = TARGET.read_text(encoding="utf-8")
if OLD not in content:
    # Try to diagnose what the actual text looks like
    idx = content.find("Already enriched")
    if idx == -1:
        sys.exit("ERROR: marker 'Already enriched' not found in file")
    snippet = content[idx - 50 : idx + 200]
    print("ACTUAL snippet repr:")
    print(repr(snippet))
    sys.exit("ERROR: OLD string not found in file — see snippet above")

new_content = content.replace(OLD, NEW, 1)
TARGET.write_text(new_content, encoding="utf-8")
print("OK: patched", TARGET)
