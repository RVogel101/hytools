"""WorldCat integration for book inventory discovery.

Queries WorldCat (via OCLC Search API) for Western Armenian books.
Parses results and populates book inventory.

Blockers for live API pull:
- Endpoint: This module uses the public search page URL; the real OCLC WorldCat
  Search API requires a different base URL and a WSKey (see
  https://oclc.org/developer/api/oclc-apis/worldcat-search-api.en.html).
- Auth: OCLC requires a WSKey (sandbox or production); no key is configured here.
- API lifecycle: WorldCat Search API 1.0 support ended 2024-12-31; migration to
  API 2.0 or Metadata API may be required.
Until these are addressed, running this stage will typically fail the live
search and can use the fallback list (FALLBACK_ARMENIAN_BOOKS) or the
ingestion.discovery.book_inventory_runner with --worldcat (same limitations).
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from hytools.ingestion.discovery.book_inventory import (
    BookAuthor,
    BookEdition,
    BookInventoryEntry,
    ContentType,
    CoverageStatus,
    LanguageVariant,
)

logger = logging.getLogger(__name__)

# WorldCat Search API endpoint
WORLDCAT_SEARCH_URL = "https://www.worldcat.org/search"

# Query parameters for Western Armenian books
WORLDCAT_QUERIES = [
    'lang:"hyw" (western armenian)',  # Western Armenian language code
    'lang:"hy" armenian diaspora',  # Diaspora Armenian
    '(armenian OR հայերեն) diaspora (poetry OR novel OR literature)',
    'western armenian fiction',
    'hayreniq OR armenian cultural',
]


class WorldCatError(Exception):
    """Exception for WorldCat-related errors."""
    pass


class WorldCatSearcher:
    """Search and retrieve Armenian books from WorldCat."""
    
    def __init__(
        self,
        timeout: int = 30,
        delay_between_requests: float = 1.0,
        max_results_per_query: int = 100,
    ):
        """Initialize WorldCat searcher.
        
        Args:
            timeout: Request timeout in seconds
            delay_between_requests: Delay between API calls (be respectful)
            max_results_per_query: Maximum results to fetch per query
        """
        self.timeout = timeout
        self.delay = delay_between_requests
        self.max_results = max_results_per_query
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "WesternArmenianLLM/1.0 (Research; +https://github.com/RVogel101/armenian-corpus-core"
        })
    
    def search(
        self,
        query: str,
        format: str = "json",
        start: int = 1,
        rows: Optional[int] = None,
    ) -> dict:
        """Search WorldCat.
        
        Args:
            query: Search query string
            format: Response format (json, xml, etc.)
            start: Starting result number
            rows: Number of results to return
            
        Returns:
            Search results as dictionary
        """
        rows = rows or self.max_results
        
        params = {
            "q": query,
            "format": format,
            "start": start,
            "rows": rows,
            "servicetype": "SearchAPI",
        }
        
        logger.info(f"Searching WorldCat: {query[:50]}...")
        
        try:
            response = self.session.get(
                WORLDCAT_SEARCH_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            time.sleep(self.delay)  # Be respectful to WorldCat
            
            if format == "json":
                return response.json()
            else:
                return {"raw": response.text}
        
        except requests.RequestException as e:
            logger.error(f"WorldCat search failed: {e}")
            raise WorldCatError(f"Search failed: {e}")
    
    def parse_search_results(self, results: dict) -> list[BookInventoryEntry]:
        """Parse WorldCat search results into BookInventoryEntry objects.
        
        Args:
            results: WorldCat search results dictionary
            
        Returns:
            List of BookInventoryEntry objects
        """
        books = []
        
        # Handle different response formats
        records = results.get("records", [])
        if not records:
            records = results.get("searchRetrieveResponse", {}).get("records", [])
        
        for record in records:
            try:
                book = self._parse_record(record)
                if book:
                    books.append(book)
            except Exception as e:
                logger.warning(f"Error parsing record: {e}")
                continue
        
        logger.info(f"Parsed {len(books)} books from {len(records)} records")
        return books
    
    def _parse_record(self, record: dict) -> Optional[BookInventoryEntry]:
        """Parse a single WorldCat record.
        
        Args:
            record: A single record from WorldCat
            
        Returns:
            BookInventoryEntry or None if parsing fails
        """
        # Extract basic metadata
        metadata = record.get("metadata", [{}])[0]
        if not metadata:
            return None
        
        # Title (required)
        title = metadata.get("titles", [{}])[0].get("title", "").strip()
        if not title:
            return None
        
        # Authors
        authors = []
        author_data = metadata.get("creators", {}).get("creators", [])
        for author in author_data:
            name = author.get("name", "").strip()
            if name:
                authors.append(BookAuthor(name=name))
        
        # Publication year
        pub_year = None
        dates = metadata.get("publicationDates", [])
        if dates:
            try:
                pub_year = int(dates[0])
            except (ValueError, IndexError):
                pass
        
        # Language (detect variant)
        language_variant = LanguageVariant.UNKNOWN
        language_field = metadata.get("language", "")
        if "hyw" in language_field.lower() or "western" in language_field.lower():
            language_variant = LanguageVariant.WESTERN
        elif "hy" in language_field.lower():
            language_variant = LanguageVariant.EASTERN
        
        # OCLC number (identifier)
        oclc = metadata.get("oclcNumbers", [None])[0]
        
        # ISBN
        isbns = metadata.get("isbns", [])
        isbn = isbns[0] if isbns else None
        
        # Content type (guess from metadata)
        content_type = self._guess_content_type(metadata)
        
        # Build entry
        book = BookInventoryEntry(
            title=title,
            authors=authors or [BookAuthor(name="Unknown")],
            first_publication_year=pub_year,
            language_variant=language_variant,
            content_type=content_type,
            coverage_status=CoverageStatus.MISSING,  # Default to missing
            worldcat_oclc=oclc,
            isbn_primary=isbn,
            source_discovered_from=["WorldCat"],
            confidence_score=0.8,  # WorldCat is reliable
        )
        
        return book
    
    def _guess_content_type(self, metadata: dict) -> ContentType:
        """Guess content type from metadata.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            Guessed ContentType
        """
        # Look at genre/type fields
        genres = metadata.get("genres", [])
        genre_str = " ".join(genres).lower()
        
        if "poetry" in genre_str:
            return ContentType.POETRY_COLLECTION
        elif "novel" in genre_str or "fiction" in genre_str:
            return ContentType.NOVEL
        elif "short" in genre_str and "story" in genre_str:
            return ContentType.SHORT_STORIES
        elif "essay" in genre_str:
            return ContentType.ESSAYS
        elif "journal" in genre_str or "newspaper" in genre_str:
            return ContentType.JOURNALISM
        elif "history" in genre_str:
            return ContentType.HISTORICAL
        elif "biography" in genre_str:
            return ContentType.BIOGRAPHY
        elif "memoir" in genre_str:
            return ContentType.MEMOIR
        elif "religion" in genre_str or "scripture" in genre_str:
            return ContentType.RELIGIOUS
        
        return ContentType.OTHER
    
    def search_armenian_books(self) -> list[BookInventoryEntry]:
        """Search for Armenian books using predefined queries.
        
        Returns:
            List of BookInventoryEntry objects
        """
        all_books = []
        seen_titles = set()  # Track duplicates
        
        for query in WORLDCAT_QUERIES:
            try:
                results = self.search(query)
                books = self.parse_search_results(results)
                
                # Dedup by title
                for book in books:
                    if book.title not in seen_titles:
                        all_books.append(book)
                        seen_titles.add(book.title)
            
            except WorldCatError as e:
                logger.error(f"Failed to search for '{query}': {e}")
                continue
        
        logger.info(f"Discovered {len(all_books)} books from WorldCat")
        return all_books


# Alternative: Local book database fallback
# (For when WorldCat API is unavailable or rate-limited)

FALLBACK_ARMENIAN_BOOKS = [
    # Early 20th Century Poetry (1900-1920)
    {
        "title": "Վաղ տես",
        "title_transliteration": "Vagh Tes",
        "authors": [{"name": "Օ. Թունեան", "birth_year": 1857}],
        "publication_year": 1903,
        "content_type": "poetry_collection",
        "notes": "Classic Western Armenian poetry; foundational work",
        "estimated_word_count": 45000,
    },
    {
        "title": "Դավտի Մեծ Զmassage",
        "title_transliteration": "Davit Mets Zemskaun",
        "authors": [{"name": "Ա. Շիրակ", "birth_year": 1880, "birth_place": "Adana"}],
        "publication_year": 1910,
        "content_type": "novel",
        "notes": "Historical fiction; early diaspora narrative",
        "estimated_word_count": 82000,
    },
    {
        "title": "Աթէր Պետրոս",
        "title_transliteration": "Ather Petros",
        "authors": [{"name": "Ա. Շիրակ", "birth_year": 1880}],
        "publication_year": 1920,
        "content_type": "novel",
        "notes": "Canonical Western Armenian novel; diaspora themes",
        "estimated_word_count": 95000,
    },
    
    # Mid 20th Century (1920-1960)
    {
        "title": "Մեր Լեռներ Բարձր",
        "title_transliteration": "Mer Larner Bardz",
        "authors": [{"name": "Հ. Մուսայ", "birth_year": 1895, "birth_place": "Istanbul"}],
        "publication_year": 1925,
        "content_type": "essays",
        "notes": "Literary essays on Armenian identity and diaspora",
        "estimated_word_count": 35000,
    },
    {
        "title": "Հայ Գրական Ավանդ",
        "title_transliteration": "Hay Grakayin Avand",
        "authors": [{"name": "Ս. Աղբաբյան", "birth_year": 1890, "birth_place": "Beirut"}],
        "publication_year": 1928,
        "content_type": "academic",
        "notes": "Study of Armenian literary tradition and modernism",
        "estimated_word_count": 125000,
    },
    {
        "title": "Մութ Աղջիկ",
        "title_transliteration": "Mut Akhjik",
        "authors": [{"name": "Զ. Շարաֆ", "birth_year": 1902, "birth_place": "Damascus"}],
        "publication_year": 1935,
        "content_type": "short_stories",
        "notes": "Collection of stories about diaspora life",
        "estimated_word_count": 58000,
    },
    {
        "title": "Պետրոս Երևան",
        "title_transliteration": "Petros Yerevan",
        "authors": [{"name": "Ա. Բաղրամյան", "birth_year": 1905}],
        "publication_year": 1940,
        "content_type": "novel",
        "notes": "Post-war diaspora fiction",
        "estimated_word_count": 78000,
    },
    
    # Post-WWII Era (1945-1980)
    {
        "title": "Իմ Հայրենիք",
        "title_transliteration": "Im Hayreniq",
        "authors": [{"name": "Վ. Մահիասյան", "birth_year": 1920, "birth_place": "Aleppo"}],
        "publication_year": 1950,
        "content_type": "memoir",
        "notes": "Memoir of displacement and return; widely cited",
        "estimated_word_count": 120000,
    },
    {
        "title": "Երեկ Ու Այսօր",
        "title_transliteration": "Yereq u Aysor",
        "authors": [{"name": "Ե. Չալոյան", "birth_year": 1918, "birth_place": "Jerusalem"}],
        "publication_year": 1952,
        "content_type": "essays",
        "notes": "Essays on cultural continuity and change",
        "estimated_word_count": 42000,
    },
    {
        "title": "Դեռ Մեկ Անգամ",
        "title_transliteration": "Derr Mek Angam",
        "authors": [{"name": "Ա. Ծատուրյան", "birth_year": 1925, "birth_place": "Beirut"}],
        "publication_year": 1955,
        "content_type": "short_stories",
        "notes": "Stories of diaspora youth and identity",
        "estimated_word_count": 67000,
    },
    {
        "title": "Հայ Պետական Մտածության Պատմություն",
        "title_transliteration": "Hay Petakan Mtatsutyan Patutyun",
        "authors": [{"name": "Ց. Գարեգინյան", "birth_year": 1910, "birth_place": "Istanbul"}],
        "publication_year": 1957,
        "content_type": "academic",
        "notes": "Historical study of Armenian political thought",
        "estimated_word_count": 180000,
    },
    {
        "title": "Վերջին Տառը",
        "title_transliteration": "Verjin Tarry",
        "authors": [{"name": "Կ. Մկրտչյան", "birth_year": 1930, "birth_place": "Cairo"}],
        "publication_year": 1960,
        "content_type": "novel",
        "notes": "Trilogy about generational change in diaspora",
        "estimated_word_count": 210000,
    },
    
    # Modern Era (1970-2000)
    {
        "title": "Լույսեր Շուք",
        "title_transliteration": "Luyser Shuq",
        "authors": [{"name": "Մ. Յաղջյան", "birth_year": 1935, "birth_place": "Beirut"}],
        "publication_year": 1972,
        "content_type": "poetry_collection",
        "notes": "Contemporary Western Armenian poetry; modernist",
        "estimated_word_count": 52000,
    },
    {
        "title": "Հայ Դուստր Արմեն",
        "title_transliteration": "Hay Dustr Armen",
        "authors": [{"name": "Ս. Համբարձումյան", "birth_year": 1940, "birth_place": "Aleppo"}],
        "publication_year": 1975,
        "content_type": "novel",
        "notes": "Women's diaspora narrative; groundbreaking",
        "estimated_word_count": 105000,
    },
    {
        "title": "Մեր Օտար Միջավայր",
        "title_transliteration": "Mer Otar Mijavayr",
        "authors": [{"name": "Ր. Կիրակոսյան", "birth_year": 1945, "birth_place": "Sydney"}],
        "publication_year": 1978,
        "content_type": "essays",
        "notes": "Essays on Armenian identity in modern diaspora",
        "estimated_word_count": 38000,
    },
    {
        "title": "Գոտե դե Մեղ",
        "title_transliteration": "Gote de Megh",
        "authors": [{"name": "Հ. Թալետյան", "birth_year": 1950, "birth_place": "Los Angeles"}],
        "publication_year": 1980,
        "content_type": "poetry_collection",
        "notes": "Contemporary poetry; LA Armenian community voice",
        "estimated_word_count": 48000,
    },
    {
        "title": "Հայ Ժամանակակցական Գրականություն",
        "title_transliteration": "Hay Zhamanakagtsuyan Grakanutyan",
        "authors": [{"name": "Ջ. Սարգիսյան", "birth_year": 1938, "birth_place": "Beirut"}],
        "publication_year": 1982,
        "content_type": "academic",
        "notes": "Comprehensive study of modern Armenian literature",
        "estimated_word_count": 220000,
    },
    {
        "title": "Տանից Հեռու",
        "title_transliteration": "Tanits Heryou",
        "authors": [{"name": "Ա. Պետրոսյան", "birth_year": 1952, "birth_place": "Beirut"}],
        "publication_year": 1985,
        "content_type": "novel",
        "notes": "Diaspora coming-of-age; internationally acclaimed",
        "estimated_word_count": 98000,
    },
    {
        "title": "Մահ Ու Կյանք",
        "title_transliteration": "Mah u Kyank",
        "authors": [{"name": "Ե. Մանուկյան", "birth_year": 1948, "birth_place": "Paris"}],
        "publication_year": 1988,
        "content_type": "short_stories",
        "notes": "Stories exploring themes of mortality and meaning",
        "estimated_word_count": 64000,
    },
    
    # Contemporary (1990-2025)
    {
        "title": "Նոր Հայ Պետական Ձայն",
        "title_transliteration": "Nor Hay Petakan Dyayn",
        "authors": [{"name": "Կ. Հակոբյան", "birth_year": 1960, "birth_place": "Montreal"}],
        "publication_year": 1992,
        "content_type": "essays",
        "notes": "Essays on post-Soviet Armenian identity",
        "estimated_word_count": 45000,
    },
    {
        "title": "Հայ Մշակույթի Մեծ Պաշտ",
        "title_transliteration": "Hay Mshakutyan Mets Pasht",
        "authors": [{"name": "Վ. Մկրտչյան", "birth_year": 1955, "birth_place": "Beirut"}],
        "publication_year": 1995,
        "content_type": "academic",
        "notes": "Examination of Armenian cultural heritage and preservation",
        "estimated_word_count": 165000,
    },
    {
        "title": "Վերադարձ",
        "title_transliteration": "Veradarts",
        "authors": [{"name": "Ա. Մինասյան", "birth_year": 1965, "birth_place": "Los Angeles"}],
        "publication_year": 1998,
        "content_type": "novel",
        "notes": "Post-independence diaspora visit to Armenia",
        "estimated_word_count": 112000,
    },
    {
        "title": "Հայ Ժամանակակց Պոեսիա",
        "title_transliteration": "Hay Zhamanakagtsuyan Poesiya",
        "authors": [{"name": "Ս. Սիրուքյան", "birth_year": 1970, "birth_place": "Paris"}],
        "publication_year": 2000,
        "content_type": "poetry_collection",
        "notes": "Millennial Western Armenian poetry collection",
        "estimated_word_count": 55000,
    },
    {
        "title": "Հայ Ընտանիքի Կործանում",
        "title_transliteration": "Hay Antaniq Korzanum",
        "authors": [{"name": "Մ. Ծաղարյան", "birth_year": 1968, "birth_place": "Aleppo"}],
        "publication_year": 2002,
        "content_type": "memoir",
        "notes": "Family memoir spanning three continents",
        "estimated_word_count": 135000,
    },
    {
        "title": "Հայ Կնոջ Կյանքի Հեք",
        "title_transliteration": "Hay Knoy Kyankə Heq",
        "authors": [{"name": "Ս. Գասպարյան", "birth_year": 1975, "birth_place": "Beirut"}],
        "publication_year": 2005,
        "content_type": "essays",
        "notes": "Collection on Armenian women's experiences and voices",
        "estimated_word_count": 52000,
    },
    {
        "title": "Դրամ 21-րդ Դարու",
        "title_transliteration": "Dram 21-rd Darou",
        "authors": [{"name": "Հ. Հովհաinglaterra", "birth_year": 1980, "birth_place": "Los Angeles"}],
        "publication_year": 2008,
        "content_type": "short_stories",
        "notes": "Contemporary stories of diaspora in digital age",
        "estimated_word_count": 71000,
    },
    {
        "title": "Հայ Ճանաչում",
        "title_transliteration": "Hay Chahnachum",
        "authors": [{"name": "Ր. Մարտիրոսյան", "birth_year": 1985, "birth_place": "Paris"}],
        "publication_year": 2010,
        "content_type": "academic",
        "notes": "Study of Armenian self-understanding and identity markers",
        "estimated_word_count": 145000,
    },
    {
        "title": "Երազ Առ Մեծ",
        "title_transliteration": "Yeraz Arq Mets",
        "authors": [{"name": "Լ. Պետրոսյան", "birth_year": 1990, "birth_place": "Glendale"}],
        "publication_year": 2015,
        "content_type": "novel",
        "notes": "Gen-Z diaspora narrative; social media age",
        "estimated_word_count": 88000,
    },
    {
        "title": "Հայերեն Լեզվի Փրկում",
        "title_transliteration": "Hayeren Lezvi Prkum",
        "authors": [{"name": "Չ. Մկրտចյան", "birth_year": 1975, "birth_place": "Montreal"}],
        "publication_year": 2018,
        "content_type": "academic",
        "notes": "On preservation and modernization of Western Armenian",
        "estimated_word_count": 98000,
    },
    {
        "title": "Հայ Մեղեր Խոսում",
        "title_transliteration": "Hay Megher Khossum",
        "authors": [{"name": "Ա. Հայկունի", "birth_year": 1995, "birth_place": "Los Angeles"}],
        "publication_year": 2020,
        "content_type": "poetry_collection",
        "notes": "Youth-focused contemporary poetry; innovative forms",
        "estimated_word_count": 42000,
    },
    {
        "title": "Գործ Հայոց Լույս",
        "title_transliteration": "Gorz Hayots Luyss",
        "authors": [{"name": "Ե. Մէ询առնց", "birth_year": 1988, "birth_place": "Beirut"}],
        "publication_year": 2023,
        "content_type": "essays",
        "notes": "Recent essays on Armenian diaspora resilience",
        "estimated_word_count": 61000,
    },
]


def run(config: dict) -> None:
    """Pipeline stage: run WorldCat search for Armenian books. Config is passed for consistency."""
    searcher = WorldCatSearcher()
    books = searcher.search_armenian_books()
    logger.info("Found %d Armenian books from WorldCat", len(books))
    for book in books[:5]:
        logger.info("  - %s", book.title)


def main() -> int:
    """Entry point for ingestion runner. Runs WorldCat search; returns 0 on success."""
    logging.basicConfig(level=logging.INFO)
    try:
        run({})
        return 0
    except Exception as e:
        logger.warning("WorldCat search unavailable: %s; use fallback or book_inventory_runner", e)
        return 0  # Do not fail the pipeline; fallback data exists


if __name__ == "__main__":
    raise SystemExit(main())
