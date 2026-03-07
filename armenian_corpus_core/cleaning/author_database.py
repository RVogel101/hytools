"""Author dialect database for tracking Western Armenian vs Eastern Armenian authors.

This module maintains structured metadata about Armenian authors to detect
when texts are attributed to or written by specific authors. This helps
identify potential dialect mixing issues—e.g., an Eastern Armenian author
attempting to write in Western Armenian without complete mastery of the dialect.

The database uses GEOGRAPHIC ORIGIN as the primary determinant of dialect:

WESTERN ARMENIAN REGIONS (Ottoman Empire / Levantine sphere):
- Eastern Turkey (Ottoman territories)
- Lebanon, Syria, Iraq, Palestine
- Egypt, Northern Africa
- Greece, Balkans
- France, Western Europe (diaspora from Ottoman collapse)
- Americas (diaspora from Ottoman collapse)

EASTERN ARMENIAN REGIONS (Persian Empire / Soviet sphere):
- Iran (Persia)
- Russian Empire territories
- South Caucasus (Caucasia) / Soviet Armenia
- Central Asia within Soviet Union

Author dialect is inferred from birthplace, family roots, and geographic center
of their literary/intellectual work. Mixed authors are noted separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class Dialect(Enum):
    """Armenian dialect classification."""
    WESTERN = "western"
    EASTERN = "eastern"
    MIXED = "mixed"  # Authors who write in both or transition
    UNKNOWN = "unknown"


class GeographicRegion(Enum):
    """Historical geographic regions that determined Armenian dialect."""
    # Western Armenian (Ottoman sphere)
    OTTOMAN_ANATOLIA = "ottoman_anatolia"  # Eastern Turkey
    LEVANT = "levant"                      # Syria, Lebanon, Palestine, Iraq
    EGYPT = "egypt"
    BALKANS = "balkans"                    # Greece, etc.
    WESTERN_EUROPE = "western_europe"      # France, etc.
    AMERICAS = "americas"                  # USA, Canada, South America
    
    # Eastern Armenian (Persian/Soviet sphere)
    PERSIA = "persia"                      # Iran
    RUSSIA = "russia"                      # Russian territories
    CAUCASIA = "caucasia"                  # South Caucasus, Soviet Armenia
    CENTRAL_ASIA = "central_asia"          # Soviet Central Asia
    
    # Mixed/Unknown
    MIXED = "mixed"
    UNKNOWN = "unknown"


def infer_dialect_from_region(region: GeographicRegion | list[GeographicRegion]) -> Dialect:
    """Infer Armenian dialect from geographic region(s).
    
    If multiple regions are given (mixed origin), returns MIXED.
    """
    if isinstance(region, list):
        if len(region) > 1:
            return Dialect.MIXED
        region = region[0] if region else GeographicRegion.UNKNOWN
    
    western_regions = {
        GeographicRegion.OTTOMAN_ANATOLIA,
        GeographicRegion.LEVANT,
        GeographicRegion.EGYPT,
        GeographicRegion.BALKANS,
        GeographicRegion.WESTERN_EUROPE,
        GeographicRegion.AMERICAS,
    }
    
    eastern_regions = {
        GeographicRegion.PERSIA,
        GeographicRegion.RUSSIA,
        GeographicRegion.CAUCASIA,
        GeographicRegion.CENTRAL_ASIA,
    }
    
    if region in western_regions:
        return Dialect.WESTERN
    elif region in eastern_regions:
        return Dialect.EASTERN
    elif region == GeographicRegion.MIXED:
        return Dialect.MIXED
    else:
        return Dialect.UNKNOWN


@dataclass
class AuthorRecord:
    """Metadata for an Armenian author."""
    
    # Name in Armenian script (Western spelling if author is WA)
    name_armenian: str
    
    # Primary geographic origin (determines dialect)
    birthplace_region: GeographicRegion
    
    # Geographic center of literary/intellectual work (may differ from birthplace)
    work_region: GeographicRegion | None = None
    
    # Inferred dialect (calculated from geographic regions)
    dialect: Dialect | None = None
    
    # Period (years active, approximately)
    period_start: int | None = None
    period_end: int | None = None
    
    # Specific city/location name (for reference)
    birthplace_city: str | None = None
    work_cities: list[str] | None = None
    
    # Literary tradition / affiliations
    # Examples: "Mekhitarist Order", "Soviet Armenian Canon", "Diaspora Literature"
    tradition: str | None = None
    
    # Notable works (for future reference)
    notable_works: list[str] | None = None
    
    # Alternate names in Armenian and transliteration
    alternate_names: list[str] | None = None
    
    # Internal note for research/verification
    notes: str | None = None
    
    def __post_init__(self):
        """Auto-compute dialect from geographic regions if not provided."""
        if self.dialect is None:
            # Use work_region if available (more important than birthplace)
            primary_region = self.work_region or self.birthplace_region
            self.dialect = infer_dialect_from_region(primary_region)



# ═══════════════════════════════════════════════════════════════════════════
# Western Armenian Authors (Ottoman Empire / Levantine geographic sphere)
# ═══════════════════════════════════════════════════════════════════════════

WESTERN_ARMENIAN_AUTHORS: dict[str, AuthorRecord] = {
    # Classical / Foundational (Mekhitarist Order, 18th-19th century)
    "Մեխիտար Սեբաստացի": AuthorRecord(
        name_armenian="Մեխիտար Սեբաստացի",
        birthplace_region=GeographicRegion.OTTOMAN_ANATOLIA,
        birthplace_city="Constantinople (Bolis)",
        work_region=GeographicRegion.WESTERN_EUROPE,
        work_cities=["Venice"],
        period_start=1676,
        period_end=1749,
        tradition="Mekhitarist Order",
        notes="Founder of Mekhitarist monastic order from Constantinople; classical WA orthography",
    ),
    
    # 19th-20th Century WA Literary Figures (Ottoman collapse diaspora)
    "Ծաղիկ Գաբրիելյան": AuthorRecord(
        name_armenian="Ծաղիկ Գաբրիելյան",
        birthplace_region=GeographicRegion.OTTOMAN_ANATOLIA,
        birthplace_city="Constantinople",
        work_region=GeographicRegion.WESTERN_EUROPE,
        work_cities=["Paris"],
        period_start=1837,
        period_end=1909,
        tradition="Diaspora Literature",
        notes="Romantic poet from Ottoman Constantinople; fled to Paris",
    ),
    
    "Տանիել Վարուճան": AuthorRecord(
        name_armenian="Տանիել Վարուճան",
        birthplace_region=GeographicRegion.OTTOMAN_ANATOLIA,
        birthplace_city="Constantinople",
        work_region=GeographicRegion.LEVANT,
        work_cities=["Beirut"],
        period_start=1884,
        period_end=1915,
        tradition="Diaspora Literature",
        notes="Poet, priest from Constantinople; worked in Beirut, killed in Armenian Genocide",
    ),
    
    "Սիամանտո": AuthorRecord(
        name_armenian="Սիամանտո",
        birthplace_region=GeographicRegion.OTTOMAN_ANATOLIA,
        birthplace_city="Constantinople",
        work_region=GeographicRegion.AMERICAS,
        work_cities=["New York"],
        period_start=1878,
        period_end=1915,
        tradition="Diaspora Literature",
        notes="Revolutionary poet from Constantinople; emigrated to USA; killed in Genocide",
    ),
    
    "Հայկ Թեքեյան": AuthorRecord(
        name_armenian="Հայկ Թեքեյան",
        birthplace_region=GeographicRegion.OTTOMAN_ANATOLIA,
        birthplace_city="Constantinople",
        work_region=GeographicRegion.WESTERN_EUROPE,
        work_cities=["Paris", "Boston"],
        period_start=1887,
        period_end=1957,
        tradition="Diaspora Literature",
        notes="Poet, intellectual from Ottoman Constantinople; active in French & American diaspora",
    ),
    
    "Շահնուր": AuthorRecord(
        name_armenian="Շահնուր",
        birthplace_region=GeographicRegion.OTTOMAN_ANATOLIA,
        birthplace_city="Constantinople",
        work_region=GeographicRegion.AMERICAS,
        work_cities=["New York", "Boston"],
        period_start=1904,
        period_end=1978,
        tradition="Diaspora Literature",
        notes="Major WA novelist from Constantinople; based in American diaspora",
    ),
    
    "Քաղ Օշական": AuthorRecord(
        name_armenian="Քաղ Օշական",
        birthplace_region=GeographicRegion.OTTOMAN_ANATOLIA,
        birthplace_city="Constantinople",
        work_region=GeographicRegion.WESTERN_EUROPE,
        work_cities=["Venice", "Jerusalem", "Paris"],
        period_start=1866,
        period_end=1951,
        tradition="Mekhitarist Order",
        notes="Mekhitarist priest-poet from Constantinople; classical WA orthography",
    ),
    
    "Զաբել Յեսայան": AuthorRecord(
        name_armenian="Զաբել Յեսայան",
        birthplace_region=GeographicRegion.OTTOMAN_ANATOLIA,
        birthplace_city="Constantinople",
        work_region=GeographicRegion.AMERICAS,
        work_cities=["Boston", "Cairo"],
        period_start=1878,
        period_end=1933,
        tradition="Diaspora Literature",
        notes="Feminist author, educator from Constantinople; worked in diaspora communities",
    ),
}


# ═══════════════════════════════════════════════════════════════════════════
# Eastern Armenian Authors (Persian Empire / Soviet geogr sphere)
# ═══════════════════════════════════════════════════════════════════════════
#
# These are authors from Iran, Russia, Soviet Armenia, and Central Asia.
# To be verified and expanded with actual EA authors from historical records.

EASTERN_ARMENIAN_AUTHORS: dict[str, AuthorRecord] = {
    # TODO: Research and populate with documented EA authors
    # Examples of regions to source from:
    # - Iranian Armenian intellectuals
    # - Russian Empire Armenian scholars
    # - Soviet Armenian literary figures from Yerevan
    # - Caucasian Armenian authors historically based in Caucasia
    #
    # Placeholder structure for future expansion:
    # "Համայա Ազգային Բանասե": AuthorRecord(
    #     name_armenian="Համայա Ազգային Բանասե",
    #     birthplace_region=GeographicRegion.CAUCASIA,
    #     birthplace_city="Yerevan",
    #     period_start=1920,
    #     period_end=1990,
    #     tradition="Soviet Armenian",
    #     notes="Soviet Armenian author from Caucasia",
    # ),
}


# ═══════════════════════════════════════════════════════════════════════════
# Mixed / Transitional Authors
# ═══════════════════════════════════════════════════════════════════════════

MIXED_DIALECT_AUTHORS: dict[str, AuthorRecord] = {
    # Authors who write in both WA and EA, or transition between them
    # TODO: Document authors with mixed or transitional dialect practices
}


def lookup_author(name: str, dialect: Dialect | None = None) -> AuthorRecord | None:
    """Look up an author by name in Western or Eastern Armenian tradition.
    
    Parameters
    ----------
    name:
        Author name (Armenian script preferred, transliteration acceptable)
    dialect:
        If specified, only search that dialect's database. If None, search all.
    
    Returns
    -------
    AuthorRecord if found, else None
    """
    search_dbs = []
    
    if dialect is None or dialect == Dialect.WESTERN:
        search_dbs.append(WESTERN_ARMENIAN_AUTHORS)
    if dialect is None or dialect == Dialect.EASTERN:
        search_dbs.append(EASTERN_ARMENIAN_AUTHORS)
    if dialect is None or dialect == Dialect.MIXED:
        search_dbs.append(MIXED_DIALECT_AUTHORS)
    
    for db in search_dbs:
        if name in db:
            return db[name]
        # Also check alternate names
        for record in db.values():
            if record.alternate_names and name in record.alternate_names:
                return record
    
    return None


def get_authors_by_dialect(dialect: Dialect) -> dict[str, AuthorRecord]:
    """Get all authors in a specific dialect tradition.
    
    Parameters
    ----------
    dialect:
        Dialect to filter by
    
    Returns
    -------
    Dictionary mapping author names to AuthorRecord objects
    """
    if dialect == Dialect.WESTERN:
        return WESTERN_ARMENIAN_AUTHORS.copy()
    elif dialect == Dialect.EASTERN:
        return EASTERN_ARMENIAN_AUTHORS.copy()
    elif dialect == Dialect.MIXED:
        return MIXED_DIALECT_AUTHORS.copy()
    return {}


def detect_author_from_text(text: str) -> tuple[AuthorRecord | None, str | None]:
    """Attempt to detect an author from text content (author name mention, etc).
    
    Scans for author names in the text. Useful for detecting when a known
    author is mentioned or when metadata indicates authorship.
    
    Parameters
    ----------
    text:
        Text to scan for author names
    
    Returns
    -------
    (AuthorRecord, name_found) or (None, None) if no author detected
    """
    for db in [WESTERN_ARMENIAN_AUTHORS, EASTERN_ARMENIAN_AUTHORS, MIXED_DIALECT_AUTHORS]:
        for name, record in db.items():
            if name in text:
                return record, name
            if record.alternate_names:
                for alt_name in record.alternate_names:
                    if alt_name in text:
                        return record, alt_name
    
    return None, None
