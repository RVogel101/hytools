"""
Metrics computation pipeline for augmentation workflow.

Integrates quantitative linguistic metrics into the augmentation process:
1. Computes metrics before augmentation (baseline)
2. Computes metrics after augmentation
3. Tracks metric changes
4. Flags quality issues
5. Stores metric cards in MongoDB (no local JSON/CSV)

All output is stored in MongoDB only. No local files or CSV exports.
Per-task metrics (compute_baseline/compute_augmented) also store to MongoDB when
mongodb_client is provided.

Usage:
    pipeline = MetricsComputationPipeline(mongodb_client=client)
    
    # Before augmentation
    baseline_metrics = pipeline.compute_baseline(original_text)
    
    # After augmentation
    augmented_metrics = pipeline.compute_augmented(
        augmented_text,
        original_text=original_text,
        strategy_name="paraphrase"
    )
    
    # Compare and analyze
    comparison = pipeline.compare_metrics(baseline_metrics, augmented_metrics)
    
    # Save to MongoDB (never to local files)
    pipeline.save_batch_report_to_mongodb(client, report)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from linguistics.metrics.text_metrics import (
    QuantitativeLinguisticsAnalyzer,
    TextMetricCard,
)


@dataclass
class MetricComparison:
    """Comparison between baseline and augmented metrics."""
    metric_name: str
    baseline_value: float
    augmented_value: float
    change: float
    percent_change: float
    direction: str  # "increase", "decrease", "stable"
    is_significant: bool  # Larger than threshold


@dataclass
class BatchMetricsReport:
    """Report for a batch of augmented texts."""
    batch_id: str
    strategy_name: str
    num_texts: int
    texts_passed_validation: int
    texts_failed_validation: int
    mean_dialect_purity: float
    mean_vocabulary_diversity: float
    mean_code_switching: float
    quality_issues: list[str]
    metric_cards: list[TextMetricCard]


class MetricsComputationPipeline:
    """Pipeline for computing and tracking metrics during augmentation.

    All output is stored in MongoDB only. No local JSON or CSV.
    """

    def __init__(
        self,
        analyzer: Optional[QuantitativeLinguisticsAnalyzer] = None,
        mongodb_client: Optional["MongoDBCorpusClient"] = None,
    ):
        """Initialize pipeline.

        Args:
            analyzer: QuantitativeLinguisticsAnalyzer instance
            mongodb_client: When provided, all metric cards and reports are stored
                in MongoDB. No local files are written.
        """
        self.analyzer = analyzer or QuantitativeLinguisticsAnalyzer()
        self.mongodb_client = mongodb_client

    def compute_baseline(
        self,
        text: str,
        text_id: str = "baseline",
        source: str = "original",
    ) -> TextMetricCard:
        """Compute metrics for baseline (original) text.
        
        Args:
            text: Original text
            text_id: Identifier for text
            source: Source of text
        
        Returns:
            TextMetricCard with metrics
        """
        return self.analyzer.analyze_text(text, text_id=text_id, source=source)

    def compute_augmented(
        self,
        augmented_text: str,
        original_text: Optional[str] = None,
        text_id: str = "augmented",
        source: str = "augmented",
        strategy_name: str = "unknown",
    ) -> TextMetricCard:
        """Compute metrics for augmented text.
        
        Args:
            augmented_text: Augmented text
            original_text: Original text (for comparison)
            text_id: Identifier for text
            source: Source of text
            strategy_name: Name of augmentation strategy (for tracking)
        
        Returns:
            TextMetricCard with metrics
        """
        metric_card = self.analyzer.analyze_text(
            augmented_text,
            text_id=f"{text_id}_{strategy_name}",
            source=source,
            original_text=original_text,
        )

        # Store in MongoDB only; no local files
        if self.mongodb_client is not None:
            card_dict = asdict(metric_card)
            self.mongodb_client.insert_augmentation_metric_card(
                text_id=f"{text_id}_{strategy_name}",
                strategy_name=strategy_name,
                card_dict=card_dict,
            )

        return metric_card

    def compare_metrics(
        self,
        baseline: TextMetricCard,
        augmented: TextMetricCard,
    ) -> dict[str, MetricComparison]:
        """Compare metrics between baseline and augmented.
        
        Args:
            baseline: Baseline (original) metric card
            augmented: Augmented metric card
        
        Returns:
            Dictionary of metric comparisons
        """
        comparisons = {}

        # Compare lexical metrics
        lexical_metrics = [
            ("ttr", baseline.lexical.ttr, augmented.lexical.ttr),
            ("sttr", baseline.lexical.sttr, augmented.lexical.sttr),
            ("vocabulary_breadth", baseline.lexical.vocabulary_breadth, augmented.lexical.vocabulary_breadth),
        ]

        for metric_name, baseline_val, augmented_val in lexical_metrics:
            comparisons[f"lexical_{metric_name}"] = self._create_comparison(
                f"lexical_{metric_name}", baseline_val, augmented_val
            )

        # Compare syntactic metrics
        syntactic_metrics = [
            ("avg_sentence_length", baseline.syntactic.avg_sentence_length, augmented.syntactic.avg_sentence_length),
            ("clauses_per_sentence", baseline.syntactic.clauses_per_sentence, augmented.syntactic.clauses_per_sentence),
        ]

        for metric_name, baseline_val, augmented_val in syntactic_metrics:
            comparisons[f"syntactic_{metric_name}"] = self._create_comparison(
                f"syntactic_{metric_name}", baseline_val, augmented_val
            )

        # Compare morphological metrics (critical for dialect)
        comparisons["morphological_em_frequency"] = self._create_comparison(
            "morphological_em_frequency",
            baseline.morphological.suffix_em_frequency,
            augmented.morphological.suffix_em_frequency,
            threshold=0.001,
        )
        comparisons["morphological_im_frequency"] = self._create_comparison(
            "morphological_im_frequency",
            baseline.morphological.suffix_im_frequency,
            augmented.morphological.suffix_im_frequency,
            threshold=0.001,
        )

        # Compare contamination metrics
        comparisons["contamination_code_switching"] = self._create_comparison(
            "contamination_code_switching",
            baseline.contamination.code_switching_index,
            augmented.contamination.code_switching_index,
            threshold=0.01,
        )

        # Compare quality flags
        comparisons["quality_dialect_purity"] = self._create_comparison(
            "quality_dialect_purity",
            baseline.quality_flags.dialect_purity_score,
            augmented.quality_flags.dialect_purity_score,
            threshold=0.05,
        )

        return comparisons

    def _create_comparison(
        self,
        metric_name: str,
        baseline_value: float,
        augmented_value: float,
        threshold: float = 0.05,
    ) -> MetricComparison:
        """Create a metric comparison."""
        change = augmented_value - baseline_value
        percent_change = (change / baseline_value * 100) if baseline_value != 0 else 0.0

        direction = "stable"
        if change > threshold:
            direction = "increase"
        elif change < -threshold:
            direction = "decrease"

        is_significant = abs(change) > threshold

        return MetricComparison(
            metric_name=metric_name,
            baseline_value=round(baseline_value, 6),
            augmented_value=round(augmented_value, 6),
            change=round(change, 6),
            percent_change=round(float(percent_change), 2),
            direction=direction,
            is_significant=is_significant,
        )

    def generate_batch_report(
        self,
        batch_id: str,
        strategy_name: str,
        metric_cards: list[TextMetricCard],
    ) -> BatchMetricsReport:
        """Generate report for a batch of augmented texts.
        
        Args:
            batch_id: Identifier for batch
            strategy_name: Augmentation strategy used
            metric_cards: List of metric cards for batch
        
        Returns:
            BatchMetricsReport summarizing batch quality
        """
        if not metric_cards:
            return BatchMetricsReport(
                batch_id=batch_id,
                strategy_name=strategy_name,
                num_texts=0,
                texts_passed_validation=0,
                texts_failed_validation=0,
                mean_dialect_purity=0.0,
                mean_vocabulary_diversity=0.0,
                mean_code_switching=0.0,
                quality_issues=[],
                metric_cards=[],
            )

        # Count validation status
        passed = sum(1 for mc in metric_cards if not mc.quality_flags.potential_issues)
        failed = len(metric_cards) - passed

        # Compute mean metrics
        mean_purity = sum(mc.quality_flags.dialect_purity_score for mc in metric_cards) / len(metric_cards)
        mean_diversity = sum(mc.lexical.ttr for mc in metric_cards) / len(metric_cards)
        mean_code_switch = sum(mc.contamination.code_switching_index for mc in metric_cards) / len(metric_cards)

        # Aggregate issues
        all_issues = []
        for mc in metric_cards:
            all_issues.extend(mc.quality_flags.potential_issues)

        issue_counts = {}
        for issue in all_issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

        quality_issues = [
            f"{count}× {issue}"
            for issue, count in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return BatchMetricsReport(
            batch_id=batch_id,
            strategy_name=strategy_name,
            num_texts=len(metric_cards),
            texts_passed_validation=passed,
            texts_failed_validation=failed,
            mean_dialect_purity=round(mean_purity, 4),
            mean_vocabulary_diversity=round(mean_diversity, 4),
            mean_code_switching=round(mean_code_switch, 6),
            quality_issues=quality_issues,
            metric_cards=metric_cards,
        )

    def save_batch_report_to_mongodb(
        self,
        client: object,
        report: BatchMetricsReport,
    ) -> str:
        """Save batch report to MongoDB. No local files.

        Args:
            client: MongoDBCorpusClient instance
            report: BatchMetricsReport to save

        Returns:
            Inserted document ID
        """
        report_dict = {
            "num_texts": report.num_texts,
            "texts_passed_validation": report.texts_passed_validation,
            "texts_failed_validation": report.texts_failed_validation,
            "mean_dialect_purity": report.mean_dialect_purity,
            "mean_vocabulary_diversity": report.mean_vocabulary_diversity,
            "mean_code_switching": report.mean_code_switching,
            "quality_issues": report.quality_issues,
            "metric_cards": [asdict(mc) for mc in report.metric_cards],
        }
        return client.insert_augmentation_metrics_report(
            batch_id=report.batch_id,
            strategy_name=report.strategy_name,
            report=report_dict,
        )

    def export_metrics_for_analysis(
        self,
        metric_cards: list[TextMetricCard],
        output_file: str = "cache/metrics_export.csv",
    ) -> None:
        """Deprecated. Metrics are stored in MongoDB only. No local CSV export."""
        raise NotImplementedError(
            "Metrics output is MongoDB-only. Query augmentation_metrics collection instead."
        )


if __name__ == "__main__":
    # Example usage
    pipeline = MetricsComputationPipeline()

    # Original text
    original = "Ես բերիմ տուն մեծ և գեղավոր։"

    # Augmented text
    augmented = "Ես բերիմ տուն որ շատ մեծ և շատ գեղավոր կար։"

    # Compute baseline
    baseline = pipeline.compute_baseline(original, text_id="example_001")
    print("✓ Baseline metrics computed")

    # Compute augmented
    aug_metrics = pipeline.compute_augmented(
        augmented,
        original_text=original,
        text_id="example_001",
        strategy_name="paraphrase",
    )
    print("✓ Augmented metrics computed")

    # Compare
    comparisons = pipeline.compare_metrics(baseline, aug_metrics)
    print("\n✓ Metric comparisons:")
    for metric_name, comparison in comparisons.items():
        if comparison.is_significant:
            print(
                f"  {metric_name}: {comparison.baseline_value:.4f} → "
                f"{comparison.augmented_value:.4f} ({comparison.direction})"
            )
