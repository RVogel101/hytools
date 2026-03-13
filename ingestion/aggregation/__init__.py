"""Aggregation: MongoDB -> derived collections (word frequencies, facets, summaries, coverage, timeline)."""

from ingestion.aggregation.coverage_analysis import CoverageAnalyzer, CoverageGap
from ingestion.aggregation.timeline_generation import TimelineGenerator, TimelineEvent

__all__ = ["CoverageAnalyzer", "CoverageGap", "TimelineGenerator", "TimelineEvent"]
