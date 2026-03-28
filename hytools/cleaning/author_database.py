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





@dataclass
class AuthorRecord:
    """Metadata for an Armenian author."""
    
    # Name in Armenian script (Western spelling if author is WA)
    name_armenian: str
    
    # Primary geographic origin (determines dialect)
    birthplace_region: GeographicRegion
    
    # Geographic center of literary/intellectual work (may differ from birthplace)
    work_region: GeographicRegion | None = None
    
    # NOTE: dialect field removed. Use `internal_language_code` and
    # `internal_language_branch` derived from writing samples only.
    internal_language_code: str | None = None
    internal_language_branch: str | None = None
    
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
    
    # NOTE: Dialect is NOT auto-inferred from geographic regions anymore.
    # The project's canonical metadata fields are `internal_language_code`
    # and `internal_language_branch`, which must be derived from an
    # author's actual writings or textual samples. If no writing samples
    # exist for the author, these fields (and `dialect`) should remain
    # unset/None rather than being inferred from birthplace/work region.
    # This avoids incorrect classification based solely on geography.



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


def lookup_author(name: str) -> AuthorRecord | None:
    """Look up an author by name across all author collections.

    This function no longer accepts a dialect parameter; authors are
    organized into collections for convenience but lookups search them all.
    """
    for db in [WESTERN_ARMENIAN_AUTHORS, EASTERN_ARMENIAN_AUTHORS, MIXED_DIALECT_AUTHORS]:
        if name in db:
            return db[name]
        # Also check alternate names
        for record in db.values():
            if record.alternate_names and name in record.alternate_names:
                return record

    return None


def get_all_authors() -> dict[str, AuthorRecord]:
    """Return a merged mapping of all known authors across collections."""
    merged: dict[str, AuthorRecord] = {}
    merged.update(WESTERN_ARMENIAN_AUTHORS)
    merged.update(EASTERN_ARMENIAN_AUTHORS)
    merged.update(MIXED_DIALECT_AUTHORS)
    return merged


def get_authors_by_dialect(dialect: str) -> dict[str, AuthorRecord]:
    """Return authors grouped by a simplified dialect key. """
    if dialect.lower() in ('western', 'western_armenian'):
        return WESTERN_ARMENIAN_AUTHORS
    if dialect.lower() in ('eastern', 'eastern_armenian'):
        return EASTERN_ARMENIAN_AUTHORS
    if dialect.lower() in ('mixed',):
        return MIXED_DIALECT_AUTHORS
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
