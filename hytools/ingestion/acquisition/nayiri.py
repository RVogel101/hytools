"""Nayiri.com dictionary scraper for Western Armenian.

Scrapes headwords and definitions from nayiri.com, an online Armenian
dictionary platform.  Uses Selenium because the site renders content
dynamically via JavaScript. Inserts directly into MongoDB.

Targets the Hayerēn-Hayerēn (Armenian-Armenian) explanatory dictionary
for WA headwords.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_NAYIRI_STAGE = "nayiri"

# All 38 Armenian lowercase letters in alphabetical order.
_ARMENIAN_LETTERS = [chr(c) for c in range(0x0561, 0x0587 + 1)]

_REQUEST_DELAY = 1.5


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


def _is_probably_blocked(page_source: str) -> bool:
    lowered = page_source.lower()
    signals = [
        "access denied",
        "temporarily blocked",
        "forbidden",
        "too many requests",
        "captcha",
        "cloudflare",
    ]
    return any(signal in lowered for signal in signals)


def _init_driver():
    """Create a headless Chrome WebDriver."""
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.webdriver import WebDriver as Chrome

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return Chrome(options=options)


def _load_checkpoint(checkpoint_path: Path) -> dict[str, dict]:
    """Load already-scraped entries keyed by headword."""
    entries: dict[str, dict] = {}
    if checkpoint_path.exists():
        with open(checkpoint_path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    entry = json.loads(line)
                    entries[entry["headword"]] = entry
                except (json.JSONDecodeError, KeyError):
                    continue
    return entries


def _extract_entries_from_page(driver) -> list[dict]:
    """Try multiple selector strategies to extract dictionary entries."""
    from selenium.webdriver.common.by import By

    entries: list[dict] = []

    selectors = [
        ".dict-result",
        ".search-result",
        ".result-entry",
        ".dict-entry",
        ".nayiri-result",
        "[class*='result']",
        "[class*='entry']",
    ]
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                text = el.text.strip()
                if not text:
                    continue
                lines = text.split("\n", 1)
                headword = lines[0].strip()
                definition = lines[1].strip() if len(lines) > 1 else ""
                if headword and any("\u0530" <= c <= "\u058F" for c in headword):
                    entries.append({"headword": headword, "definition": definition})
            if entries:
                return entries
        except Exception:
            continue

    # Strategy 2: parse bold/strong headwords from page body
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        lines = body_text.split("\n")
        for line in lines:
            line = line.strip()
            if line and any("\u0530" <= c <= "\u058F" for c in line[:5]) and len(line) < 100:
                entries.append({"headword": line, "definition": ""})
    except Exception:
        pass

    return entries


def scrape_dictionary(config: dict, client) -> int:
    """Scrape Armenian-Armenian dictionary entries via two-letter prefix search.

    Inserts directly into MongoDB. Returns the number of new entries inserted.
    """
    from hytools.ingestion._shared.helpers import insert_or_skip

    nayiri_cfg = config.get("scraping", {}).get("nayiri", {})
    request_delay = float(nayiri_cfg.get("request_delay", _REQUEST_DELAY))
    max_prefixes = nayiri_cfg.get("max_prefixes")
    max_retries = int(nayiri_cfg.get("max_retries", 3))
    retry_base_delay = float(nayiri_cfg.get("retry_base_delay", 2.0))
    consecutive_fail_limit = int(nayiri_cfg.get("consecutive_fail_limit", 30))
    cooldown_seconds = int(nayiri_cfg.get("cooldown_seconds", 43200))

    meta = _load_nayiri_metadata(client)
    if meta.get("status") == "blocked":
        blocked_at = int(meta.get("timestamp", 0))
        elapsed = int(time.time()) - blocked_at
        if elapsed < cooldown_seconds:
            remaining = cooldown_seconds - elapsed
            logger.warning(
                "Nayiri scraper is in cooldown due to prior block. Try again in ~%d seconds.",
                remaining,
            )
            return 0

    existing = _load_existing_headwords(client)
    done_prefixes = set(meta.get("done", []))
    logger.info("Nayiri checkpoint has %d existing entries in MongoDB", len(existing))

    driver = _init_driver()
    new_count = 0

    try:
        processed_prefixes = 0
        consecutive_failures = 0
        for first_letter in _ARMENIAN_LETTERS:
            for second_letter in _ARMENIAN_LETTERS:
                prefix = first_letter + second_letter
                if prefix in done_prefixes:
                    continue
                if max_prefixes is not None and processed_prefixes >= int(max_prefixes):
                    logger.info("Reached max_prefixes=%s; stopping early", max_prefixes)
                    _save_nayiri_metadata(client, "ok", sorted(done_prefixes))
                    return new_count

                url = f"http://nayiri.com/search?l=hy_HY&query={prefix}&dt=HH"

                loaded = False
                for attempt in range(max_retries):
                    try:
                        driver.get(url)
                        time.sleep(request_delay)
                        if _is_probably_blocked(driver.page_source):
                            _save_nayiri_metadata(client, "blocked", sorted(done_prefixes))
                            logger.warning("Nayiri appears to be blocking requests; entering cooldown")
                            return new_count
                        loaded = True
                        break
                    except Exception as exc:
                        if attempt < max_retries - 1:
                            backoff = retry_base_delay * (2 ** attempt)
                            logger.warning(
                                "Failed to load %s (attempt %d/%d): %s; backing off %.1fs",
                                url,
                                attempt + 1,
                                max_retries,
                                exc,
                                backoff,
                            )
                            time.sleep(backoff)
                        else:
                            logger.warning("Failed to load %s after %d attempts", url, max_retries)

                if not loaded:
                    consecutive_failures += 1
                    if consecutive_failures >= consecutive_fail_limit:
                        _save_nayiri_metadata(client, "blocked", sorted(done_prefixes))
                        logger.warning("Consecutive failure limit reached; marking as blocked")
                        return new_count
                    continue

                consecutive_failures = 0

                page_entries = _extract_entries_from_page(driver)
                for entry in page_entries:
                    hw = entry["headword"]
                    if hw in existing:
                        continue
                    definition = entry.get("definition", "")
                    text = f"{hw}\n{definition}" if definition else hw
                    if insert_or_skip(
                        client,
                        source="nayiri",
                        title=hw,
                        text=text,
                        url=f"http://nayiri.com/search?l=hy_HY&query={hw}&dt=HH",
                        metadata={
                            "source_type": "dictionary",
                            "prefix_query": prefix,
                        },
                        config=config,
                    ):
                        new_count += 1
                        existing.add(hw)

                done_prefixes.add(prefix)
                processed_prefixes += 1
                if processed_prefixes % 20 == 0:
                    _save_nayiri_metadata(client, "ok", sorted(done_prefixes))

            logger.info(
                "Letter %s complete — %d total entries (%d new)",
                first_letter, len(existing), new_count,
            )

        _save_nayiri_metadata(client, "ok", sorted(done_prefixes))
    finally:
        driver.quit()

    logger.info("Nayiri scrape complete: %d total entries (%d new)", len(existing), new_count)
    return new_count


def run(config: dict) -> None:
    """Entry-point: scrape Nayiri dictionary."""
    from hytools.ingestion._shared.helpers import open_mongodb_client

    with open_mongodb_client(config) as client:
        if client is None:
            raise RuntimeError("MongoDB connection required but unavailable")
        inserted = scrape_dictionary(config, client)
        logger.info("Nayiri MongoDB: %d new entries inserted", inserted)
