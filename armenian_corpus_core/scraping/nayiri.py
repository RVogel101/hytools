"""Nayiri.com dictionary scraper for Western Armenian.

Scrapes headwords and definitions from nayiri.com, an online Armenian
dictionary platform.  Uses Selenium because the site renders content
dynamically via JavaScript.

Targets the Hayerēn-Hayerēn (Armenian-Armenian) explanatory dictionary
for WA headwords, then enriches with Armenian-English translations.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_STATUS_FILE = ".status.json"
_PREFIX_CHECKPOINT = ".prefix_checkpoint.json"

# All 38 Armenian lowercase letters in alphabetical order.
_ARMENIAN_LETTERS = [chr(c) for c in range(0x0561, 0x0587 + 1)]

_REQUEST_DELAY = 1.5


def _load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def _record_status(output_dir: Path, status: str, details: str = "") -> None:
    status_path = output_dir / _STATUS_FILE
    payload = {
        "status": status,
        "details": details,
        "timestamp": int(time.time()),
    }
    _save_json(status_path, payload)


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


def scrape_dictionary(config: dict, output_dir: Path) -> int:
    """Scrape Armenian-Armenian dictionary entries via two-letter prefix search.

    Returns the number of entries scraped.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    nayiri_cfg = config.get("scraping", {}).get("nayiri", {})
    request_delay = float(nayiri_cfg.get("request_delay", _REQUEST_DELAY))
    max_prefixes = nayiri_cfg.get("max_prefixes")
    max_retries = int(nayiri_cfg.get("max_retries", 3))
    retry_base_delay = float(nayiri_cfg.get("retry_base_delay", 2.0))
    consecutive_fail_limit = int(nayiri_cfg.get("consecutive_fail_limit", 30))
    cooldown_seconds = int(nayiri_cfg.get("cooldown_seconds", 43200))

    status = _load_json(output_dir / _STATUS_FILE, default={})
    if status.get("status") == "blocked":
        blocked_at = int(status.get("timestamp", 0))
        elapsed = int(time.time()) - blocked_at
        if elapsed < cooldown_seconds:
            remaining = cooldown_seconds - elapsed
            logger.warning(
                "Nayiri scraper is in cooldown due to prior block. Try again in ~%d seconds.",
                remaining,
            )
            return 0

    checkpoint_path = output_dir / "dictionary.jsonl"
    prefix_checkpoint_path = output_dir / _PREFIX_CHECKPOINT
    existing = _load_checkpoint(checkpoint_path)
    prefix_checkpoint = _load_json(prefix_checkpoint_path, default={"done": []})
    done_prefixes = set(prefix_checkpoint.get("done", []))
    logger.info("Nayiri checkpoint has %d existing entries", len(existing))

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
                    return new_count

                url = f"http://nayiri.com/search?l=hy_HY&query={prefix}&dt=HH"

                loaded = False
                for attempt in range(max_retries):
                    try:
                        driver.get(url)
                        time.sleep(request_delay)
                        if _is_probably_blocked(driver.page_source):
                            _record_status(
                                output_dir,
                                "blocked",
                                f"Block signal detected on prefix={prefix}",
                            )
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
                        _record_status(
                            output_dir,
                            "blocked",
                            f"Consecutive failures exceeded limit ({consecutive_fail_limit})",
                        )
                        logger.warning("Consecutive failure limit reached; marking as blocked")
                        return new_count
                    continue

                consecutive_failures = 0

                page_entries = _extract_entries_from_page(driver)
                for entry in page_entries:
                    hw = entry["headword"]
                    if hw in existing:
                        continue
                    entry["prefix_query"] = prefix
                    existing[hw] = entry

                    with open(checkpoint_path, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    new_count += 1

                done_prefixes.add(prefix)
                processed_prefixes += 1
                if processed_prefixes % 20 == 0:
                    _save_json(prefix_checkpoint_path, {"done": sorted(done_prefixes)})

            logger.info(
                "Letter %s complete — %d total entries (%d new)",
                first_letter, len(existing), new_count,
            )

        _save_json(prefix_checkpoint_path, {"done": sorted(done_prefixes)})
        _record_status(output_dir, "ok", "Dictionary scrape completed")
    finally:
        driver.quit()

    logger.info("Nayiri scrape complete: %d total entries (%d new)", len(existing), new_count)
    return new_count


def enrich_with_english(
    dictionary_path: Path,
    output_path: Path,
) -> int:
    """Query Nayiri Armenian-English dictionary for each headword.

    Returns the number of entries enriched with English translations.
    """
    if not dictionary_path.exists():
        logger.warning("No dictionary file found at %s", dictionary_path)
        return 0

    entries = _load_checkpoint(dictionary_path)
    driver = _init_driver()
    enriched_count = 0

    try:
        for hw, entry in entries.items():
            if entry.get("english"):
                enriched_count += 1
                continue

            url = f"http://nayiri.com/search?l=en&query={hw}&dt=HE"
            try:
                driver.get(url)
                time.sleep(_REQUEST_DELAY)
                page_entries = _extract_entries_from_page(driver)
                if page_entries:
                    entry["english"] = page_entries[0].get("definition", "")
                    enriched_count += 1
            except Exception:
                continue
    finally:
        driver.quit()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(list(entries.values()), fh, ensure_ascii=False, indent=2)

    logger.info("Enriched %d / %d entries with English translations", enriched_count, len(entries))
    return enriched_count


def run(config: dict) -> None:
    """Entry-point: scrape Nayiri dictionary."""
    raw_dir = Path(config["paths"]["raw_dir"]) / "nayiri"

    scrape_dictionary(config, raw_dir)

    dictionary_path = raw_dir / "dictionary.jsonl"
    if dictionary_path.exists():
        enrich_with_english(dictionary_path, raw_dir / "dictionary_enriched.json")
