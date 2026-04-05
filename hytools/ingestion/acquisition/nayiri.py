"""Nayiri data import helpers for Western Armenian.

This module provides sanctioned import paths for Nayiri's published
datasets (the Lexicon JSON and the Western Armenian Corpus ZIP).
All web-scraping code has been removed to respect Nayiri's usage
preferences; use `import_lexicon_from_url` and `import_corpus_from_url`
to load official data releases into MongoDB.
"""

from __future__ import annotations

import logging
import time
import json
import io
import zipfile
import hashlib
from pathlib import Path

import requests

_MAX_DOWNLOAD_RETRIES = 3
_RETRY_SLEEP_SECONDS = 2


logger = logging.getLogger(__name__)

_NAYIRI_STAGE = "nayiri"

# Note: scraping functionality has been removed to respect Nayiri's
# request not to be scraped. Only sanctioned download/import functions
# (lexicon and corpus imports) and light metadata helpers remain in this
# module.


def _load_nayiri_metadata(client) -> dict:
    """Load status and prefix checkpoint from MongoDB metadata."""
    if client is None:
        return {"status": "ok", "done": [], "timestamp": 0}
    entry = client.metadata.find_one({"stage": _NAYIRI_STAGE})
    if not entry:
        return {"status": "ok", "done": [], "timestamp": 0}
    return {
        "status": entry.get("status", "ok"),
        "done": list(entry.get("done", [])),
        "timestamp": int(entry.get("timestamp", 0)),
    }


def _save_nayiri_metadata(client, status: str, done: list[str]) -> None:
    """Save status and prefix checkpoint to MongoDB metadata."""
    if client is None:
        return
    from datetime import datetime, timezone
    client.metadata.replace_one(
        {"stage": _NAYIRI_STAGE},
        {
            "stage": _NAYIRI_STAGE,
            "status": status,
            "done": done,
            "timestamp": int(time.time()),
            "updated_at": datetime.now(timezone.utc),
        },
        upsert=True,
    )


def _load_existing_headwords(client) -> set[str]:
    """Load already-scraped headwords from MongoDB."""
    if client is None:
        return set()
    cursor = client.documents.find(
        {"source": "nayiri"},
        {"title": 1},
    )
    return {doc.get("title", "") for doc in cursor if doc.get("title")}


# Scraping functions removed.


def _parse_json_value(value):
    """Try parsing a JSON string; return original on failure."""
    if isinstance(value, str):
        raw = value.strip()
        for attempt in (raw, raw.strip('"')):
            try:
                return json.loads(attempt)
            except Exception:
                logger.debug("JSON parse attempt failed for value: %.50s", attempt)
                continue
        # If there are escaped quotes, attempt a relaxed parse.
        try:
            candidate = raw.replace('\\"', '"')
            return json.loads(candidate)
        except Exception:
            logger.debug("Relaxed JSON parse also failed for value: %.50s", raw)
            return value
    return value


def _parse_properties_and_content(raw_text: str) -> tuple[dict, str]:
    """Parse leading key=value properties and return (meta_dict, content_text).

    Looks for a marker line `BEGIN_DOCUMENT_CONTENT` and falls back to parsing
    initial key=value lines until the first blank line.
    """
    marker = "BEGIN_DOCUMENT_CONTENT"
    meta: dict = {}
    content = raw_text
    if marker in raw_text:
        props, content = raw_text.split(marker, 1)
        for ln in props.splitlines():
            if "=" in ln:
                k, v = ln.split("=", 1)
                meta[k.strip().lower()] = v.strip()
        return meta, content

    # Fallback: initial key=value lines until blank line
    lines = raw_text.splitlines()
    props_lines = []
    for ln in lines[:30]:
        if not ln.strip():
            break
        if "=" in ln:
            props_lines.append(ln)
    if props_lines:
        idx = len(props_lines)
        for ln in props_lines:
            k, v = ln.split("=", 1)
            meta[k.strip().lower()] = v.strip()
        content = "\n".join(lines[idx:])
    return meta, content


def parse_lexicon_data(data: dict, client) -> int:
    """Parse a Nayiri lexicon JSON-like dict and upsert entries into `nayiri_entries`.

    Returns the number of newly inserted entries (upserts).
    """
    imported = 0
    if not isinstance(data, dict):
        return 0

    # Build inflections map if present (inflectionId -> object)
    inflections_map = {}
    if "inflections" in data and isinstance(data["inflections"], list):
        for inf in data["inflections"]:
            inf_id = inf.get("inflectionId") or inf.get("id")
            if inf_id:
                inflections_map[str(inf_id)] = inf

    # Locate lexemes list
    lexemes = data.get("lexemes") or data.get("lemmas") or []
    coll = client.db.get_collection("nayiri_entries")
    metadata_top = data.get("metadata") or {}

    for lex in lexemes:
        if not isinstance(lex, dict):
            continue
        lexeme_id = lex.get("lexemeId") or lex.get("id") or lex.get("lexeme_id")
        for lemma in lex.get("lemmas") or []:
            if not isinstance(lemma, dict):
                continue
            lemma_id = lemma.get("lemmaId") or lemma.get("id") or lemma.get("lemma_id")
            lemma_str = lemma.get("lemmaString") or lemma.get("lemma") or lemma.get("headword")
            pos = lemma.get("partOfSpeech") or lemma.get("pos")
            word_forms = []
            resolved_inflections = []
            for wf in lemma.get("wordForms") or []:
                if isinstance(wf, dict):
                    form = wf.get("s") or wf.get("form") or wf.get("string")
                    inf_id = wf.get("i") or wf.get("inflectionId")
                    if form:
                        word_forms.append(form)
                    if inf_id and str(inf_id) in inflections_map:
                        resolved_inflections.append(inflections_map[str(inf_id)])
                elif isinstance(wf, str):
                    word_forms.append(wf)

            content_text = lemma.get("definitions") or lemma.get("definition") or ""
            content_text = content_text if isinstance(content_text, str) else json.dumps(content_text, ensure_ascii=False)
            content_sha1 = hashlib.sha1(content_text.encode("utf-8")).hexdigest()

            entry_id = f"nayiri:{lexeme_id or 'unknown'}:{lemma_id or hashlib.md5((lemma_str or '').encode()).hexdigest()[:8]}"
            doc = {
                "entry_id": entry_id,
                "lexeme_id": lexeme_id,
                "lexeme_description": lex.get("description"),
                "lexeme_type": lex.get("lemmaType"),
                "lemma_id": lemma_id,
                "headword": lemma_str or "",
                "part_of_speech": pos,
                "lemma_display_string": lemma.get("lemmaDisplayString"),
                "lemma_num_word_forms": lemma.get("numWordForms"),
                "word_forms": word_forms,
                "inflections": resolved_inflections or None,
                "definition": content_text,
                "content_sha1": content_sha1,
                "metadata": {"source": "nayiri", "nayiri_metadata": metadata_top or {}},
            }

            try:
                res = coll.update_one({"entry_id": entry_id}, {"$set": doc}, upsert=True)
                if getattr(res, "upserted_id", None) is not None:
                    imported += 1
            except Exception:
                logger.debug("MongoDB upsert failed for nayiri entry %s", entry_id, exc_info=True)
                continue

    return imported


def parse_corpus_member(member: str, raw_text: str, authors_map: dict, pubs_map: dict, client) -> bool:
    """Parse a single `data-store/<member>` raw text and insert into Mongo via client.insert_document.

    Returns True if insert succeeded, False otherwise.
    """
    meta, content = _parse_properties_and_content(raw_text)
    author_id = meta.get("author") or meta.get("author_id")
    author = authors_map.get(author_id, author_id) if author_id else None
    pub_id = meta.get("publication") or meta.get("publication_id")
    publication = pubs_map.get(pub_id, pub_id) if pub_id else None

    try:
        nayiri_meta = {"file": member, **({k: v for k, v in meta.items()} if meta else {})}
        # Preserve original document ID from Nayiri metadata when available
        if "id" in meta:
            nayiri_meta["id"] = meta.get("id")

        logger.debug("Parsing corpus member %s with meta %s", member, nayiri_meta)

        client.insert_document(
            source="nayiri_wa_corpus",
            title=Path(member).name,
            text=content.strip(),
            author=_parse_json_value(author) if author else None,
            metadata={
                "nayiri": nayiri_meta,
                "publication": _parse_json_value(publication) if publication else None,
            },
        )
        logger.debug("Inserted corpus member %s", member)
        return True
    except Exception as exc:
        logger.error("Error inserting corpus member %s: %s", member, exc)
        return False



def import_lexicon_from_url(config: dict, client) -> int:
    """Download Nayiri lexicon ZIP (JSON) and import into `nayiri_entries` collection.

    The function attempts to map common lexicon fields to the sqlite-style
    `nayiri_entries` schema used elsewhere in the project.
    """
    nayiri_cfg = config.get("scraping", {}).get("nayiri", {})

    cache_dir = Path(config.get("cache_dir", "cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / "nayiri_lexicon.zip"

    # Local cache override path (preferred). If lexicon_path exists, skip HTTP download entirely.
    # If lexicon_path is relative, resolve it against configured cache_dir for predictability.
    lexicon_path = None
    raw_lexicon_path = nayiri_cfg.get("lexicon_path", "")
    if raw_lexicon_path:
        candidate = Path(raw_lexicon_path).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        lexicon_path = candidate.resolve()

    if lexicon_path and lexicon_path.exists():
        logger.info("Using local Nayiri lexicon from %s", lexicon_path)
        zip_path = lexicon_path
    elif zip_path.exists():
        logger.info("Using existing cache lexicon ZIP from %s", zip_path)
    else:
        url = nayiri_cfg.get(
            "lexicon_url",
            "https://www.nayiri.com/nayiri-armenian-lexicon-2026-02-15-v1.json.zip",
        )

        for attempt in range(1, _MAX_DOWNLOAD_RETRIES + 1):
            try:
                logger.info("Downloading Nayiri lexicon (attempt %d/%d) from %s", attempt, _MAX_DOWNLOAD_RETRIES, url)
                with requests.get(url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(zip_path, "wb") as fh:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                fh.write(chunk)
                logger.info("Successfully downloaded Nayiri lexicon on attempt %d", attempt)
                break
            except Exception as exc:
                logger.warning("Nayiri lexicon download attempt %d failed: %s", attempt, exc)
                if attempt == _MAX_DOWNLOAD_RETRIES:
                    logger.error("Failed to download Nayiri lexicon after %d attempts", _MAX_DOWNLOAD_RETRIES)
                    return 0
                time.sleep(_RETRY_SLEEP_SECONDS * attempt)


    imported = 0
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            json_name = next((n for n in zf.namelist() if n.lower().endswith(".json")), None)
            if not json_name:
                logger.error("No JSON file found inside downloaded Nayiri ZIP")
                return 0
            with zf.open(json_name) as jf:
                data = json.load(io.TextIOWrapper(jf, encoding="utf-8"))

            # Build inflections map if present (inflectionId -> object)
            inflections_map = {}
            if isinstance(data, dict):
                for k in ("inflections",):
                    if k in data and isinstance(data[k], list):
                        for inf in data[k]:
                            inf_id = inf.get("inflectionId") or inf.get("id")
                            if inf_id:
                                inflections_map[str(inf_id)] = inf

            # Locate lexemes list (Nayiri's schema uses top-level 'lexemes')
            lexemes = []
            if isinstance(data, dict):
                if "lexemes" in data and isinstance(data["lexemes"], list):
                    lexemes = data["lexemes"]
                elif "lemmas" in data and isinstance(data["lemmas"], list):
                    lexemes = data["lemmas"]
            elif isinstance(data, list):
                lexemes = data

            coll = client.db.get_collection("nayiri_entries")
            metadata_top = data.get("metadata") if isinstance(data, dict) else {}

            for lex in lexemes:
                if not isinstance(lex, dict):
                    continue
                lexeme_id = lex.get("lexemeId") or lex.get("id") or lex.get("lexeme_id")
                lemmas = lex.get("lemmas") or []
                for lemma in lemmas:
                    if not isinstance(lemma, dict):
                        continue
                    lemma_id = lemma.get("lemmaId") or lemma.get("id") or lemma.get("lemma_id")
                    lemma_str = lemma.get("lemmaString") or lemma.get("lemma") or lemma.get("headword")
                    pos = lemma.get("partOfSpeech") or lemma.get("pos")
                    word_forms = []
                    resolved_inflections = []
                    for wf in lemma.get("wordForms") or []:
                        if isinstance(wf, dict):
                            form = wf.get("s") or wf.get("form") or wf.get("string")
                            inf_id = wf.get("i") or wf.get("inflectionId")
                            if form:
                                word_forms.append(form)
                            if inf_id and str(inf_id) in inflections_map:
                                resolved_inflections.append(inflections_map[str(inf_id)])
                        elif isinstance(wf, str):
                            word_forms.append(wf)

                    content_text = lemma.get("definitions") or lemma.get("definition") or ""
                    content_text = (
                        content_text if isinstance(content_text, str) else json.dumps(content_text, ensure_ascii=False)
                    )
                    content_sha1 = hashlib.sha1(content_text.encode("utf-8")).hexdigest()

                    entry_id = f"nayiri:{lexeme_id or 'unknown'}:{lemma_id or hashlib.md5((lemma_str or '').encode()).hexdigest()[:8]}"

                    doc = {
                        "entry_id": entry_id,
                        "lexeme_id": lexeme_id,
                        "lexeme_description": lex.get("description"),
                        "lexeme_type": lex.get("lemmaType"),
                        "lemma_id": lemma_id,
                        "headword": lemma_str or "",
                        "part_of_speech": pos,
                        "lemma_display_string": lemma.get("lemmaDisplayString"),
                        "lemma_num_word_forms": lemma.get("numWordForms"),
                        "word_forms": word_forms,
                        "inflections": resolved_inflections or None,
                        "definition": content_text,
                        "content_sha1": content_sha1,
                        "metadata": {
                            "source": "nayiri",
                            "nayiri_metadata": metadata_top or {},
                        },
                    }

                    try:
                        res = coll.update_one({"entry_id": entry_id}, {"$set": doc}, upsert=True)
                        # Count newly upserted documents
                        if getattr(res, "upserted_id", None) is not None:
                            imported += 1
                    except Exception as exc:
                        logger.debug("Skipping Nayiri lexicon entry due to insert error: %s", exc)
                        continue
    except Exception as exc:
        logger.error("Error importing Nayiri lexicon: %s", exc)
        return imported

    if not nayiri_cfg.get("lexicon_keep_zip", False):
        try:
            zip_path.unlink()
        except Exception:
            logger.debug("Failed to remove lexicon ZIP %s", zip_path, exc_info=True)

    logger.info("Imported %d Nayiri lexicon entries into nayiri_entries collection", imported)
    return imported


def import_corpus_from_url(config: dict, client) -> int:
    """Download Nayiri Western Armenian corpus ZIP and import into `nayiri_wa_corpus` collection.

    Expects the ZIP to contain a `data-store/` folder with one text file per document,
    and `authors.properties` and `publications.properties` alongside it.
    """
    nayiri_cfg = config.get("scraping", {}).get("nayiri", {})
    cache_dir = Path(config.get("cache_dir", "cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / "nayiri_corpus.zip"

    # Local cache override path (preferred). If corpus_path exists, skip HTTP download entirely.
    # If corpus_path is relative, resolve it against configured cache_dir for predictability.
    corpus_path = None
    raw_corpus_path = nayiri_cfg.get("corpus_path", "")
    if raw_corpus_path:
        candidate = Path(raw_corpus_path).expanduser()
        if not candidate.is_absolute():
            candidate = Path.cwd() / candidate
        corpus_path = candidate.resolve()

    if corpus_path and corpus_path.exists():
        logger.info("Using local Nayiri corpus from %s", corpus_path)
        zip_path = corpus_path
    elif zip_path.exists():
        logger.info("Using existing cache corpus ZIP from %s", zip_path)
    else:
        url = nayiri_cfg.get(
            "corpus_url",
            "https://www.nayiri.com/nayiri-corpus-of-western-armenian-2026-02-25-v2.zip",
        )

        for attempt in range(1, _MAX_DOWNLOAD_RETRIES + 1):
            try:
                logger.info("Downloading Nayiri corpus (attempt %d/%d) from %s", attempt, _MAX_DOWNLOAD_RETRIES, url)
                with requests.get(url, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(zip_path, "wb") as fh:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                fh.write(chunk)
                logger.info("Successfully downloaded Nayiri corpus on attempt %d", attempt)
                break
            except Exception as exc:
                logger.warning("Nayiri corpus download attempt %d failed: %s", attempt, exc)
                if attempt == _MAX_DOWNLOAD_RETRIES:
                    logger.error("Failed to download Nayiri corpus after %d attempts", _MAX_DOWNLOAD_RETRIES)
                    return 0
                time.sleep(_RETRY_SLEEP_SECONDS * attempt)


    imported = 0
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # load authors and publications props if present
            authors_map = {}
            pubs_map = {}
            for name in ("authors.properties", "publications.properties"):
                if name in zf.namelist():
                    with zf.open(name) as pf:
                        for raw in pf.read().decode("utf-8").splitlines():
                            if "=" in raw:
                                k, v = raw.split("=", 1)
                                if name.startswith("authors"):
                                    authors_map[k.strip()] = v.strip()
                                else:
                                    pubs_map[k.strip()] = v.strip()

            # import files under data-store/
            for member in zf.namelist():
                if not member.startswith("data-store/"):
                    continue
                with zf.open(member) as mf:
                    raw_text = mf.read().decode("utf-8", errors="replace")
                    if parse_corpus_member(member, raw_text, authors_map, pubs_map, client):
                        imported += 1
                    else:
                        logger.debug("Skipping corpus doc %s due to parse/insert failure", member)

    except Exception as exc:
        logger.error("Error importing Nayiri corpus: %s", exc)
        return imported

    if not nayiri_cfg.get("corpus_keep_zip", False):
        try:
            zip_path.unlink()
        except Exception:
            logger.debug("Failed to remove corpus ZIP %s", zip_path, exc_info=True)

    logger.info("Imported %d documents into nayiri_wa_corpus collection", imported)
    return imported
def run(config: dict) -> None:
    """Entry-point: import Nayiri data.

    Supported modes (set `scraping.nayiri.mode`):
        - "lexicon"  -> download and import the official Lexicon JSON
        - "corpus"   -> download and import the Corpus of Western Armenian

    Scraping of nayiri.com is intentionally disabled.
    """
    from hytools.ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB connection required but unavailable")
        nayiri_cfg = config.get("scraping", {}).get("nayiri", {})

        # When mode is not explicit, prefer local file availability to prevent unnecessary network.
        if "mode" not in nayiri_cfg or not nayiri_cfg.get("mode"):
            lexicon_path = nayiri_cfg.get("lexicon_path")
            corpus_path = nayiri_cfg.get("corpus_path")
            if lexicon_path and Path(lexicon_path).expanduser().resolve().exists():
                mode = "lexicon"
            elif corpus_path and Path(corpus_path).expanduser().resolve().exists():
                mode = "corpus"
            else:
                mode = "lexicon"
        else:
            mode = nayiri_cfg.get("mode")

        if mode == "lexicon":
            inserted = import_lexicon_from_url(config, client)
            logger.info("Nayiri lexicon imported: %d entries", inserted)
        elif mode == "corpus":
            inserted = import_corpus_from_url(config, client)
            logger.info("Nayiri corpus imported: %d documents", inserted)
        else:
            raise RuntimeError(f"Unsupported nayiri.mode='{mode}': scraping is disabled")
