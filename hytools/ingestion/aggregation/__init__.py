"""Aggregation: MongoDB -> derived collections (word frequencies, facets, summaries, coverage, timeline)."""

from hytools.ingestion.aggregation.coverage_analysis import CoverageAnalyzer, CoverageGap
from hytools.ingestion.aggregation.timeline_generation import TimelineGenerator, TimelineEvent

__all__ = ["CoverageAnalyzer", "CoverageGap", "TimelineGenerator", "TimelineEvent"]
