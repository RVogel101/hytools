"""Author biography enrichment via Wikipedia and other sources.

Enriches author profiles with:
- Birth/death dates and places
- Biography summaries
- Known works lists
- External links
"""

from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import quote

import requests

from hytool.ingestion.discovery.author_research import AuthorProfile

logger = logging.getLogger(__name__)


class BiographyEnricher:
    """Enrich author profiles with biographical data."""
    
    def __init__(
        self,
        timeout: int = 30,
        delay_between_requests: float = 1.0,
    ):
        """Initialize enricher.
        
        Args:
            timeout: Request timeout in seconds
            delay_between_requests: Delay between API calls
        """
        self.timeout = timeout
        self.delay = delay_between_requests
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "WesternArmenianLLM/1.0 (Research; +https://github.com/litni/WesternArmenianLLM)"
        })
    
    def enrich_from_wikipedia(
        self,
        profile: AuthorProfile,
        prefer_western: bool = True,
    ) -> AuthorProfile:
        """Enrich profile from Wikipedia.
        
        Args:
            profile: AuthorProfile to enrich
            prefer_western: Try Western Armenian Wikipedia (hyw) first
            
        Returns:
            Enriched AuthorProfile
        """
        # Try different Wikipedia editions
        wikis = ["hyw", "hy", "en"] if prefer_western else ["hy", "hyw", "en"]
        
        for wiki in wikis:
            try:
                data = self._search_wikipedia(profile.primary_name, wiki)
                
                if data:
                    profile = self._apply_wikipedia_data(profile, data, wiki)
                    profile.research_sources.append(f"wikipedia:{wiki}")
                    logger.info(f"Enriched {profile.primary_name} from {wiki}.wikipedia.org")
                    break
            
            except Exception as e:
                logger.warning(f"Wikipedia {wiki} lookup failed for {profile.primary_name}: {e}")
                continue
        
        time.sleep(self.delay)
        return profile
    
    def _search_wikipedia(
        self,
        name: str,
        wiki: str = "hyw",
    ) -> Optional[dict]:
        """Search Wikipedia for author.
        
        Args:
            name: Author name to search
            wiki: Wikipedia language code
            
        Returns:
            Wikipedia page data or None
        """
        # Use Wikipedia API
        url = f"https://{wiki}.wikipedia.org/w/api.php"
        
        # Search for page
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": name,
            "format": "json",
            "srlimit": 1,
        }
        
        try:
            response = self.session.get(url, params=search_params, timeout=self.timeout)
            response.raise_for_status()
            
            search_data = response.json()
            search_results = search_data.get("query", {}).get("search", [])
            
            if not search_results:
                return None
            
            # Get page title
            page_title = search_results[0]["title"]
            
            # Fetch page data
            page_params = {
                "action": "query",
                "titles": page_title,
                "prop": "extracts|pageprops",
                "exintro": True,
                "format": "json",
            }
            
            response = self.session.get(url, params=page_params, timeout=self.timeout)
            response.raise_for_status()
            
            page_data = response.json()
            pages = page_data.get("query", {}).get("pages", {})
            
            if pages:
                page_id = list(pages.keys())[0]
                return pages[page_id]
            
        except requests.RequestException as e:
            logger.error(f"Wikipedia API error: {e}")
        
        return None
    
    def _apply_wikipedia_data(
        self,
        profile: AuthorProfile,
        data: dict,
        wiki: str,
    ) -> AuthorProfile:
        """Apply Wikipedia data to profile.
        
        Args:
            profile: AuthorProfile to update
            data: Wikipedia page data
            wiki: Wikipedia language code
            
        Returns:
            Updated profile
        """
        # Extract intro text
        extract = data.get("extract", "")
        
        # Parse dates from extract (simplified)
        import re
        
        # Look for birth year pattern (1880-1950)
        birth_match = re.search(r"\b(18\d{2}|19\d{2})\b", extract)
        if birth_match and not profile.birth_year:
            profile.birth_year = int(birth_match.group(1))
            profile.confidence_birth = 0.7
        
        # Look for death year (typically later in text)
        death_match = re.search(r"հրաժեշտ\s*–?\s*(\d{4})|մահ\s*–?\s*(\d{4})|died\s*(\d{4})", extract.lower())
        if death_match and not profile.death_year:
            year = death_match.group(1) or death_match.group(2) or death_match.group(3)
            if year:
                profile.death_year = int(year)
                profile.confidence_death = 0.6
        
        # Extract place names (cities)
        places = re.findall(r"[Ա-Ֆ][ա-ֆ]{3,15}", extract)
        if places and not profile.birth_place:
            # Take first significant place name
            for place in places[:3]:
                if len(place) > 3:
                    profile.birth_place = place
                    break
        
        # Add notes
        if extract:
            profile.notes += f"\n\nWikipedia ({wiki}): {extract[:200]}..."
        
        # Update profile completeness
        if profile.birth_year and profile.death_year:
            profile.profile_complete = True
        
        return profile
    
    def enrich_batch(
        self,
        profiles: list[AuthorProfile],
        max_profiles: Optional[int] = None,
    ) -> list[AuthorProfile]:
        """Enrich multiple profiles.
        
        Args:
            profiles: List of AuthorProfile objects
            max_profiles: Optional limit on how many to enrich
            
        Returns:
            List of enriched profiles
        """
        enriched = []
        count = 0
        
        for profile in profiles:
            if max_profiles and count >= max_profiles:
                break
            
            try:
                enriched_profile = self.enrich_from_wikipedia(profile)
                enriched.append(enriched_profile)
                count += 1
            
            except Exception as e:
                logger.error(f"Error enriching {profile.primary_name}: {e}")
                enriched.append(profile)  # Add unenriched
        
        logger.info(f"Enriched {count}/{len(profiles)} profiles")
        return enriched


class ManualBiographyDatabase:
    """Manually curated biographical data fallback."""
    
    # Canonical Western Armenian authors with known data
    KNOWN_AUTHORS = {
        "Օ. Թունեան": {
            "birth_year": 1857,
            "birth_place": "Կամախ",
            "death_year": 1930,
            "death_place": "Վենետիկ",
            "writing_period": (1890, 1930),
            "genres": ["poetry", "prose"],
            "confidence": 1.0,
        },
        "Ա. Շիրակ": {
            "birth_year": 1880,
            "birth_place": "Ադանա",
            "death_year": 1968,
            "death_place": "Յունաստան",
            "writing_period": (1905, 1965),
            "genres": ["novel", "short_stories"],
            "confidence": 1.0,
        },
        "Զապէլ Եսայեան": {
            "birth_year": 1878,
            "birth_place": "Մալաթիա",
            "death_year": 1943,
            "death_place": "Փարիզ",
            "writing_period": (1900, 1943),
            "genres": ["novel", "journalism"],
            "confidence": 1.0,
        },
        "Գրիգոր Զոհրապ": {
            "birth_year": 1861,
            "birth_place": "Կ. Պոլիս",
            "death_year": 1915,
            "death_place": "unknown",
            "writing_period": (1885, 1915),
            "genres": ["short_stories", "essays", "journalism"],
            "confidence": 1.0,
        },
    }
    
    @classmethod
    def enrich_from_manual_data(cls, profile: AuthorProfile) -> AuthorProfile:
        """Enrich profile from manual database.
        
        Args:
            profile: AuthorProfile to enrich
            
        Returns:
            Enriched profile
        """
        # Check if we have manual data
        data = cls.KNOWN_AUTHORS.get(profile.primary_name)
        
        if not data:
            return profile
        
        # Apply data
        profile.birth_year = data["birth_year"]
        profile.birth_place = data["birth_place"]
        profile.death_year = data.get("death_year")
        profile.death_place = data.get("death_place")
        profile.writing_period_start = data["writing_period"][0]
        profile.writing_period_end = data["writing_period"][1]
        profile.genres = data["genres"]
        profile.confidence_birth = data["confidence"]
        profile.confidence_death = data["confidence"]
        profile.confidence_writing_period = data["confidence"]
        profile.research_sources.append("manual_database")
        profile.flags.append("canonical")
        profile.profile_complete = True
        
        logger.info(f"Enriched {profile.primary_name} from manual database")
        return profile


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    from hytool.ingestion.discovery.author_research import AuthorProfile
    
    # Example usage
    enricher = BiographyEnricher()
    
    profile = AuthorProfile(
        author_id="tunean1857",
        primary_name="Օ. Թունեան",
    )
    
    # Try manual enrichment first
    profile = ManualBiographyDatabase.enrich_from_manual_data(profile)
    
    print(f"Enriched profile:")
    print(f"  Name: {profile.primary_name}")
    print(f"  Birth: {profile.birth_year} in {profile.birth_place}")
    print(f"  Death: {profile.death_year}")
    print(f"  Writing period: {profile.writing_period_start}-{profile.writing_period_end}")

