"""Coverage analysis for author and work representation in corpus.

Analyzes:
- Which canonical authors are missing
- Which time periods are underrepresented
- Which genres lack coverage
- Work coverage by author
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from hytool.ingestion.discovery.author_research import AuthorProfile, AuthorProfileManager
from hytool.ingestion.discovery.book_inventory import BookInventoryManager, ContentType, CoverageStatus

logger = logging.getLogger(__name__)


@dataclass
class CoverageGap:
    """Identified coverage gap."""
    gap_type: str  # author, period, genre, work
    priority: str  # high, medium, low
    description: str
    recommended_action: str
    impact_score: float = 0.0  # 0-1, estimated impact of filling gap
    metadata: dict = field(default_factory=dict)


class CoverageAnalyzer:
    """Analyze corpus coverage and identify gaps."""
    
    def __init__(
        self,
        profile_manager: AuthorProfileManager,
        inventory_manager: Optional[BookInventoryManager] = None,
    ):
        """Initialize coverage analyzer.
        
        Args:
            profile_manager: AuthorProfileManager instance
            inventory_manager: Optional BookInventoryManager instance
        """
        self.profile_manager = profile_manager
        self.inventory_manager = inventory_manager
        self.gaps: list[CoverageGap] = []
    
    def analyze_author_coverage(self) -> list[CoverageGap]:
        """Identify missing or underrepresented authors.
        
        Returns:
            List of CoverageGap objects
        """
        gaps = []
        
        # Check canonical authors
        canonical = self.profile_manager.find_canonical_authors()
        
        for profile in canonical:
            # Check if author has works in corpus
            coverage_pct = profile.corpus_coverage_percentage
            
            if coverage_pct == 0:
                gaps.append(CoverageGap(
                    gap_type="author",
                    priority="high",
                    description=f"Canonical author {profile.primary_name} has no works in corpus",
                    recommended_action=f"Acquire at least one major work by {profile.primary_name}",
                    impact_score=0.9,
                    metadata={
                        "author_name": profile.primary_name,
                        "author_id": profile.author_id,
                        "known_works": profile.known_works_count,
                    },
                ))
            
            elif coverage_pct < 25:
                gaps.append(CoverageGap(
                    gap_type="author",
                    priority="medium",
                    description=f"{profile.primary_name} only {coverage_pct:.1f}% represented",
                    recommended_action=f"Add more works by {profile.primary_name}",
                    impact_score=0.6,
                    metadata={
                        "author_name": profile.primary_name,
                        "coverage_percentage": coverage_pct,
                    },
                ))
        
        logger.info(f"Identified {len(gaps)} author coverage gaps")
        return gaps
    
    def analyze_period_coverage(self) -> list[CoverageGap]:
        """Identify underrepresented time periods.
        
        Returns:
            List of CoverageGap objects
        """
        gaps = []
        
        # Count authors by period
        period_counts = defaultdict(int)
        period_corpus_counts = defaultdict(int)
        
        for profile in self.profile_manager.profiles.values():
            year = profile.writing_period_start or profile.birth_year
            
            if not year:
                continue
            
            # Assign to period
            if year < 1900:
                period = "pre-1900"
            elif year < 1925:
                period = "1900-1924"
            elif year < 1950:
                period = "1925-1949"
            elif year < 1975:
                period = "1950-1974"
            elif year < 2000:
                period = "1975-1999"
            else:
                period = "2000+"
            
            period_counts[period] += 1
            
            if profile.corpus_coverage_percentage > 0:
                period_corpus_counts[period] += 1
        
        # Identify gaps
        for period, total in period_counts.items():
            in_corpus = period_corpus_counts.get(period, 0)
            coverage_pct = (in_corpus / total * 100) if total > 0 else 0
            
            if coverage_pct < 30:
                priority = "high" if coverage_pct == 0 else "medium"
                
                gaps.append(CoverageGap(
                    gap_type="period",
                    priority=priority,
                    description=f"Period {period}: only {coverage_pct:.1f}% of authors represented in corpus",
                    recommended_action=f"Acquire works from {period} period",
                    impact_score=0.7 if coverage_pct == 0 else 0.5,
                    metadata={
                        "period": period,
                        "total_authors": total,
                        "authors_in_corpus": in_corpus,
                    },
                ))
        
        logger.info(f"Identified {len(gaps)} period coverage gaps")
        return gaps
    
    def analyze_genre_coverage(self) -> list[CoverageGap]:
        """Identify underrepresented genres.
        
        Returns:
            List of CoverageGap objects
        """
        gaps = []
        
        # Count by genre
        genre_counts = Counter()
        genre_corpus_counts = Counter()
        
        for profile in self.profile_manager.profiles.values():
            for genre in profile.genres:
                genre_counts[genre] += 1
                
                if profile.corpus_coverage_percentage > 0:
                    genre_corpus_counts[genre] += 1
        
        # Identify gaps
        for genre, total in genre_counts.items():
            in_corpus = genre_corpus_counts.get(genre, 0)
            coverage_pct = (in_corpus / total * 100) if total > 0 else 0
            
            if coverage_pct < 40:
                priority = "high" if coverage_pct == 0 else "medium"
                
                gaps.append(CoverageGap(
                    gap_type="genre",
                    priority=priority,
                    description=f"Genre '{genre}': only {coverage_pct:.1f}% of authors represented",
                    recommended_action=f"Acquire more {genre} works",
                    impact_score=0.6,
                    metadata={
                        "genre": genre,
                        "total_authors": total,
                        "authors_in_corpus": in_corpus,
                    },
                ))
        
        logger.info(f"Identified {len(gaps)} genre coverage gaps")
        return gaps
    
    def analyze_work_coverage(self) -> list[CoverageGap]:
        """Identify missing works from book inventory.
        
        Returns:
            List of CoverageGap objects
        """
        gaps = []
        
        if not self.inventory_manager:
            logger.warning("No inventory manager provided; skipping work coverage analysis")
            return gaps
        
        # Check books marked as MISSING or COPYRIGHTED
        for book in self.inventory_manager.books:
            if book.coverage_status == CoverageStatus.MISSING:
                # Determine priority based on content type and author
                priority = "high" if book.content_type in [
                    ContentType.NOVEL,
                    ContentType.POETRY_COLLECTION,
                    ContentType.SHORT_STORIES,
                ] else "medium"
                
                author_names = ", ".join([a.name for a in book.authors])
                
                gaps.append(CoverageGap(
                    gap_type="work",
                    priority=priority,
                    description=f"Missing work: '{book.title}' by {author_names} ({book.first_publication_year})",
                    recommended_action=f"Locate and acquire '{book.title}'",
                    impact_score=0.7 if priority == "high" else 0.4,
                    metadata={
                        "title": book.title,
                        "authors": author_names,
                        "year": book.first_publication_year,
                        "content_type": book.content_type.value,
                    },
                ))
            
            elif book.coverage_status == CoverageStatus.COPYRIGHTED:
                gaps.append(CoverageGap(
                    gap_type="work",
                    priority="low",
                    description=f"Copyrighted work: '{book.title}' (cannot acquire)",
                    recommended_action="Document copyright status; consider fair use excerpts",
                    impact_score=0.2,
                    metadata={
                        "title": book.title,
                        "status": "copyrighted",
                    },
                ))
        
        logger.info(f"Identified {len(gaps)} work coverage gaps")
        return gaps
    
    def generate_comprehensive_analysis(self) -> list[CoverageGap]:
        """Run all coverage analyses.
        
        Returns:
            Combined list of all gaps
        """
        all_gaps = []
        
        all_gaps.extend(self.analyze_author_coverage())
        all_gaps.extend(self.analyze_period_coverage())
        all_gaps.extend(self.analyze_genre_coverage())
        all_gaps.extend(self.analyze_work_coverage())
        
        # Sort by priority and impact score
        priority_order = {"high": 3, "medium": 2, "low": 1}
        all_gaps.sort(
            key=lambda g: (priority_order.get(g.priority, 0), g.impact_score),
            reverse=True,
        )
        
        logger.info(f"Generated comprehensive analysis: {len(all_gaps)} total gaps")
        return all_gaps
    
    def export_gaps_report(
        self,
        output_file: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> int:
        """Persist coverage gaps report to MongoDB. No file output.
        
        Args:
            output_file: Ignored; retained for API compatibility.
            config: Pipeline config with database.mongodb_uri; required for persistence.
            
        Returns:
            1 if saved to MongoDB, 0 otherwise.
        """
        gaps = self.generate_comprehensive_analysis()
        report: dict[str, Any] = {
            "summary": {
                "total_gaps": len(gaps),
                "by_priority": {
                    "high": len([g for g in gaps if g.priority == "high"]),
                    "medium": len([g for g in gaps if g.priority == "medium"]),
                    "low": len([g for g in gaps if g.priority == "low"]),
                },
                "by_type": {
                    "author": len([g for g in gaps if g.gap_type == "author"]),
                    "period": len([g for g in gaps if g.gap_type == "period"]),
                    "genre": len([g for g in gaps if g.gap_type == "genre"]),
                    "work": len([g for g in gaps if g.gap_type == "work"]),
                },
            },
            "gaps": [
                {
                    "type": g.gap_type,
                    "priority": g.priority,
                    "description": g.description,
                    "recommended_action": g.recommended_action,
                    "impact_score": g.impact_score,
                    "metadata": g.metadata,
                }
                for g in gaps
            ],
        }
        if not (config and config.get("database", {}).get("mongodb_uri")):
            logger.warning("MongoDB not configured; coverage gaps not persisted (no file output)")
            return 0
        try:
            from hytool.ingestion._shared.helpers import open_mongodb_client
        except ImportError:
            logger.warning("ingestion._shared.helpers not available; coverage gaps not saved")
            return 0
        with open_mongodb_client(config) as client:
            if client is None:
                return 0
            client.save_coverage_gaps(report)
        logger.info("Saved coverage gaps report to MongoDB coverage_gaps")
        return 1
    
    def export_priority_checklist(
        self,
        output_file: Optional[str] = None,
        priority_filter: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> int:
        """Persist acquisition priorities to MongoDB (schema: all + high + medium + low rows). No file output.
        
        Args:
            output_file: Ignored; retained for API compatibility.
            priority_filter: Ignored; all segments (all, high, medium, low) are saved in one doc.
            config: Pipeline config with database.mongodb_uri; required for persistence.
            
        Returns:
            1 if saved to MongoDB, 0 otherwise.
        """
        gaps = self.generate_comprehensive_analysis()
        def row(g: CoverageGap) -> dict[str, Any]:
            return {
                "priority": g.priority,
                "type": g.gap_type,
                "description": g.description,
                "action": g.recommended_action,
                "impact_score": round(g.impact_score, 2),
            }
        priorities_by_filter: dict[str, list[dict]] = {
            "all": [row(g) for g in gaps],
            "high": [row(g) for g in gaps if g.priority == "high"],
            "medium": [row(g) for g in gaps if g.priority == "medium"],
            "low": [row(g) for g in gaps if g.priority == "low"],
        }
        if not (config and config.get("database", {}).get("mongodb_uri")):
            logger.warning("MongoDB not configured; acquisition priorities not persisted (no file output)")
            return 0
        try:
            from hytool.ingestion._shared.helpers import open_mongodb_client
        except ImportError:
            logger.warning("ingestion._shared.helpers not available; priorities not saved")
            return 0
        with open_mongodb_client(config) as client:
            if client is None:
                return 0
            client.save_acquisition_priorities(priorities_by_filter)
        logger.info("Saved acquisition priorities to MongoDB acquisition_priorities")
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
        corpus_coverage_percentage=0,  # Not in corpus
        flags=["canonical"],
    ))
    
    # Analyze coverage
    analyzer = CoverageAnalyzer(manager)
    gaps = analyzer.analyze_author_coverage()
    
    print(f"Found {len(gaps)} coverage gaps:")
    for gap in gaps:
        print(f"  [{gap.priority}] {gap.description}")

