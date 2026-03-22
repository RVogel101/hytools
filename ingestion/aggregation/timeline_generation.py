"""Timeline generation for author chronological analysis.

Creates:
- Author life event timelines
- Publication timelines
- Historical period analysis
- Generation-based groupings
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from hytool.ingestion.discovery.author_research import AuthorProfile, AuthorProfileManager

logger = logging.getLogger(__name__)


@dataclass
class TimelineEvent:
    """Single event on timeline."""
    year: int
    event_type: str  # birth, death, first_publication, major_work, historical
    author_name: str
    description: str
    significance: str = ""  # Optional context


class TimelineGenerator:
    """Generate chronological timelines for authors."""
    
    def __init__(self, profile_manager: AuthorProfileManager):
        """Initialize timeline generator.
        
        Args:
            profile_manager: AuthorProfileManager instance
        """
        self.profile_manager = profile_manager
        self.events: list[TimelineEvent] = []
    
    def generate_author_lifespans(self) -> list[TimelineEvent]:
        """Generate timeline of author lifespans.
        
        Returns:
            List of TimelineEvent objects
        """
        events = []
        
        for profile in self.profile_manager.profiles.values():
            # Birth event
            if profile.birth_year:
                events.append(TimelineEvent(
                    year=profile.birth_year,
                    event_type="birth",
                    author_name=profile.primary_name,
                    description=f"{profile.primary_name} born" + (f" in {profile.birth_place}" if profile.birth_place else ""),
                ))
            
            # Death event
            if profile.death_year:
                events.append(TimelineEvent(
                    year=profile.death_year,
                    event_type="death",
                    author_name=profile.primary_name,
                    description=f"{profile.primary_name} died" + (f" in {profile.death_place}" if profile.death_place else ""),
                ))
        
        # Sort by year
        events.sort(key=lambda e: e.year)
        
        logger.info(f"Generated {len(events)} lifespan events")
        return events
    
    def generate_writing_periods(self) -> list[TimelineEvent]:
        """Generate timeline of writing/publication periods.
        
        Returns:
            List of TimelineEvent objects
        """
        events = []
        
        for profile in self.profile_manager.profiles.values():
            if profile.writing_period_start:
                events.append(TimelineEvent(
                    year=profile.writing_period_start,
                    event_type="first_publication",
                    author_name=profile.primary_name,
                    description=f"{profile.primary_name} began publishing",
                    significance=f"Genres: {', '.join(profile.genres[:3])}" if profile.genres else "",
                ))
            
            if profile.writing_period_end and profile.writing_period_end != profile.writing_period_start:
                events.append(TimelineEvent(
                    year=profile.writing_period_end,
                    event_type="last_publication",
                    author_name=profile.primary_name,
                    description=f"{profile.primary_name} last known publication",
                ))
        
        events.sort(key=lambda e: e.year)
        
        logger.info(f"Generated {len(events)} writing period events")
        return events
    
    def generate_period_analysis(
        self,
        decade_grouping: bool = True,
    ) -> dict[str, list[str]]:
        """Analyze authors by historical period.
        
        Args:
            decade_grouping: Group by decades if True, else by quarter-century
            
        Returns:
            Dictionary mapping periods to author lists
        """
        periods: dict[str, list[str]] = defaultdict(list)
        
        for profile in self.profile_manager.profiles.values():
            # Use writing period or birth year
            year = profile.writing_period_start or profile.birth_year
            
            if not year:
                periods["unknown"].append(profile.primary_name)
                continue
            
            # Determine period
            if decade_grouping:
                period_start = (year // 10) * 10
                period_key = f"{period_start}s"
            else:
                if year < 1900:
                    period_key = "pre-1900"
                elif year < 1925:
                    period_key = "1900-1924"
                elif year < 1950:
                    period_key = "1925-1949"
                elif year < 1975:
                    period_key = "1950-1974"
                elif year < 2000:
                    period_key = "1975-1999"
                else:
                    period_key = "2000+"
            
            periods[period_key].append(profile.primary_name)
        
        logger.info(f"Grouped authors into {len(periods)} periods")
        return dict(periods)
    
    def generate_generation_analysis(self) -> dict[str, list[str]]:
        """Analyze authors by literary generation.
        
        Western Armenian literary generations:
        - Classical (pre-1900): Traditional forms
        - Genocide Generation (1900-1920): Witness literature
        - Diaspora First Wave (1920-1950): Exile and identity
        - Post-WWII (1950-1975): New diaspora centers
        - Modern (1975-2000): Contemporary forms
        - Contemporary (2000+): Digital age
        
        Returns:
            Dictionary mapping generations to author lists
        """
        generations: dict[str, list[str]] = defaultdict(list)
        
        for profile in self.profile_manager.profiles.values():
            # Use birth year for generation
            year = profile.birth_year
            
            if not year:
                generations["unknown"].append(profile.primary_name)
                continue
            
            # Assign generation
            if year < 1870:
                generation = "Classical (pre-1900)"
            elif year < 1890:
                generation = "Genocide Generation (1870-1915)"
            elif year < 1920:
                generation = "Diaspora First Wave (1890-1950)"
            elif year < 1950:
                generation = "Post-WWII (1920-1975)"
            elif year < 1975:
                generation = "Modern (1950-2000)"
            else:
                generation = "Contemporary (1975+)"
            
            generations[generation].append(profile.primary_name)
        
        logger.info(f"Grouped authors into {len(generations)} generations")
        return dict(generations)
    
    def add_historical_context(
        self,
        events: list[TimelineEvent],
    ) -> list[TimelineEvent]:
        """Add historical context events to timeline.
        
        Args:
            events: Existing timeline events
            
        Returns:
            Timeline with historical events added
        """
        # Key historical events for Western Armenian literature
        historical_events = [
            TimelineEvent(
                year=1915,
                event_type="historical",
                author_name="",
                description="Armenian Genocide begins",
                significance="Watershed moment for Western Armenian literature",
            ),
            TimelineEvent(
                year=1922,
                event_type="historical",
                author_name="",
                description="Smyrna catastrophe; major diaspora wave",
                significance="Diaspora literature centers shift to Beirut, Paris, US",
            ),
            TimelineEvent(
                year=1991,
                event_type="historical",
                author_name="",
                description="Armenian independence",
                significance="New connections between diaspora and homeland",
            ),
        ]
        
        # Merge and sort
        all_events = events + historical_events
        all_events.sort(key=lambda e: e.year)
        
        return all_events
    
    def export_timeline_json(
        self,
        output_file: Optional[str] = None,
        include_historical: bool = True,
        config: Optional[dict] = None,
    ) -> int:
        """Persist timeline to MongoDB. No local file output.
        
        Args:
            output_file: Ignored; retained for API compatibility.
            include_historical: Include historical context events
            config: Pipeline config with database.mongodb_uri; required for persistence.
            
        Returns:
            1 if saved to MongoDB, 0 otherwise.
        """
        events = []
        events.extend(self.generate_author_lifespans())
        events.extend(self.generate_writing_periods())
        if include_historical:
            events = self.add_historical_context(events)
        events.sort(key=lambda e: e.year)
        timeline_data = {
            "timeline": [
                {
                    "year": e.year,
                    "type": e.event_type,
                    "author": e.author_name,
                    "description": e.description,
                    "significance": e.significance,
                }
                for e in events
            ],
            "metadata": {
                "total_events": len(events),
                "year_range": (events[0].year, events[-1].year) if events else (None, None),
                "authors_count": len(self.profile_manager.profiles),
            },
        }
        if not (config and config.get("database", {}).get("mongodb_uri")):
            logger.warning("MongoDB not configured; timeline not persisted (no file output)")
            return 0
        try:
            from hytool.ingestion._shared.helpers import open_mongodb_client
        except ImportError:
            logger.warning("ingestion._shared.helpers not available; timeline not saved")
            return 0
        with open_mongodb_client(config) as client:
            if client is None:
                return 0
            client.save_author_timeline(timeline_data)
        logger.info("Saved timeline (%d events) to MongoDB author_timeline", len(events))
        return 1
    
    def export_period_analysis_csv(
        self,
        output_file: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> int:
        """Persist period analysis to MongoDB (schema: periods dict). No file output.
        
        Args:
            output_file: Ignored; retained for API compatibility.
            config: Pipeline config with database.mongodb_uri; required for persistence.
            
        Returns:
            1 if saved to MongoDB, 0 otherwise.
        """
        periods = self.generate_period_analysis(decade_grouping=True)
        period_doc: dict[str, Any] = {
            "periods": {k: list(v) for k, v in periods.items()},
            "period_counts": {k: len(v) for k, v in periods.items()},
        }
        if not (config and config.get("database", {}).get("mongodb_uri")):
            logger.warning("MongoDB not configured; period analysis not persisted (no file output)")
            return 0
        try:
            from hytool.ingestion._shared.helpers import open_mongodb_client
        except ImportError:
            logger.warning("ingestion._shared.helpers not available; period analysis not saved")
            return 0
        with open_mongodb_client(config) as client:
            if client is None:
                return 0
            client.save_author_period_analysis(period_doc)
        logger.info("Saved period analysis to MongoDB author_period_analysis")
        return 1
    
    def export_generation_report(
        self,
        output_file: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> int:
        """Persist generation report to MongoDB. No file output.
        
        Args:
            output_file: Ignored; retained for API compatibility.
            config: Pipeline config with database.mongodb_uri; required for persistence.
            
        Returns:
            1 if saved to MongoDB, 0 otherwise.
        """
        generations = self.generate_generation_analysis()
        report = {
            "generations": {
                gen: {"count": len(authors), "authors": authors}
                for gen, authors in generations.items()
            },
            "metadata": {
                "total_authors": sum(len(authors) for authors in generations.values()),
                "generation_count": len(generations),
            },
        }
        if not (config and config.get("database", {}).get("mongodb_uri")):
            logger.warning("MongoDB not configured; generation report not persisted (no file output)")
            return 0
        try:
            from hytool.ingestion._shared.helpers import open_mongodb_client
        except ImportError:
            logger.warning("ingestion._shared.helpers not available; generation report not saved")
            return 0
        with open_mongodb_client(config) as client:
            if client is None:
                return 0
            client.save_author_generation_report(report)
        logger.info("Saved generation report to MongoDB author_generation_report")
        return 1


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    from hytool.ingestion.discovery.author_research import AuthorProfile, AuthorProfileManager
    
    # Example usage
    manager = AuthorProfileManager()
    
    # Add sample authors
    manager.add_profile(AuthorProfile(
        author_id="tunean1857",
        primary_name="Օ. Թունեան",
        birth_year=1857,
        death_year=1930,
        writing_period_start=1890,
        writing_period_end=1930,
        genres=["poetry"],
    ))
    
    # Generate timeline
    generator = TimelineGenerator(manager)
    events = generator.generate_author_lifespans()
    
    print(f"Generated {len(events)} timeline events")
    for event in events[:5]:
        print(f"  {event.year}: {event.description}")

