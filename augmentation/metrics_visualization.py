"""
Visualization and analysis tools for quantitative linguistic metrics.

Provides visualization functions for:
1. Metric distributions (histograms, boxplots)
2. Comparative analysis (augmented vs original)
3. Quality scoring visualizations
4. Anomaly detection visualization
5. Statistical reports and summaries
"""

from __future__ import annotations

from typing import Optional
from pathlib import Path
import json
import warnings

import numpy as np

from linguistics.metrics import TextMetricCard
from augmentation.baseline_statistics import CorpusBaselineStatistics, MetricStatistics


def plot_metric_distribution(
    metric_cards: list[TextMetricCard],
    metric_name: str,
    baseline_stats: Optional[CorpusBaselineStatistics] = None,
    output_file: Optional[str] = None,
    title: Optional[str] = None,
) -> Optional[str]:
    """Plot distribution of a single metric across texts.
    
    Args:
        metric_cards: List of metric cards
        metric_name: Name of metric to visualize (e.g., "lexical_ttr")
        baseline_stats: Baseline statistics for reference
        output_file: Output file path (optional)
        title: Custom title (optional)
    
    Returns:
        Path to saved image or None if matplotlib not available
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore[reportUnknownReturnType]
    except ImportError:  # type: ignore[reportUnknownReturnType]
        warnings.warn("matplotlib not installed; skipping visualization")
        return None

    # Extract metric values
    values = _extract_metric_values(metric_cards, metric_name)
    
    if not values:
        warnings.warn(f"No values found for metric: {metric_name}")
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot histogram
    ax.hist(values, bins="auto", alpha=0.7, color="steelblue", edgecolor="black")
    
    # Add baseline reference lines if available
    if baseline_stats:
        baseline_metric_stats = _get_metric_stats(baseline_stats, metric_name)
        if baseline_metric_stats:
            ax.axvline(
                baseline_metric_stats.mean,
                color="red",
                linestyle="--",
                linewidth=2,
                label=f"Baseline Mean: {baseline_metric_stats.mean:.4f}",
            )
            # Add 1σ and 2σ bands
            mean = baseline_metric_stats.mean
            std = baseline_metric_stats.std_dev
            ax.axvline(mean + std, color="orange", linestyle=":", linewidth=1, alpha=0.7)
            ax.axvline(mean - std, color="orange", linestyle=":", linewidth=1, alpha=0.7)

    ax.set_xlabel(metric_name, fontsize=12)
    ax.set_ylabel("Frequency", fontsize=12)
    ax.set_title(title or f"Distribution of {metric_name}")
    if ax.get_legend_handles_labels()[0]:
        ax.legend()
    ax.grid(True, alpha=0.3)

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return str(output_path)

    return None


def plot_metric_comparison(
    baseline_cards: list[TextMetricCard],
    augmented_cards: list[TextMetricCard],
    metric_name: str,
    output_file: Optional[str] = None,
) -> Optional[str]:
    """Plot comparison of metric between baseline and augmented texts.
    
    Args:
        baseline_cards: Baseline metric cards
        augmented_cards: Augmented metric cards
        metric_name: Metric to compare
        output_file: Output file path (optional)
    
    Returns:
        Path to saved image or None if matplotlib not available
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore[reportUnknownReturnType]
    except ImportError:
        warnings.warn("matplotlib not installed; skipping visualization")
        return None

    baseline_values = _extract_metric_values(baseline_cards, metric_name)
    augmented_values = _extract_metric_values(augmented_cards, metric_name)
    
    if not baseline_values or not augmented_values:
        warnings.warn(f"Insufficient data for metric: {metric_name}")
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Create boxplot
    data_to_plot = [baseline_values, augmented_values]
    bp = ax.boxplot(
        data_to_plot,
        patch_artist=True,
        widths=0.6,
    )
    ax.set_xticklabels(["Baseline", "Augmented"])
    
    # Color boxes
    colors = ["lightblue", "lightgreen"]
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)

    ax.set_ylabel(metric_name, fontsize=12)
    ax.set_title(f"Comparison of {metric_name}: Baseline vs Augmented")
    ax.grid(True, alpha=0.3, axis="y")

    # Add mean values
    baseline_mean = np.mean(baseline_values)
    aug_mean = np.mean(augmented_values)
    ax.plot([1], [baseline_mean], "r*", markersize=15, label=f"Mean: {baseline_mean:.4f}")
    ax.plot([2], [aug_mean], "g*", markersize=15, label=f"Mean: {aug_mean:.4f}")
    if ax.get_legend_handles_labels()[0]:
        ax.legend()

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return str(output_path)

    return None


def plot_quality_scores(
    metric_cards: list[TextMetricCard],
    output_file: Optional[str] = None,
) -> Optional[str]:
    """Plot quality score distribution.
    
    Args:
        metric_cards: List of metric cards
        output_file: Output file path (optional)
    
    Returns:
        Path to saved image or None if matplotlib not available
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore[reportUnknownReturnType]
    except ImportError:
        warnings.warn("matplotlib not installed; skipping visualization")
        return None

    dialect_purity = [mc.quality_flags.dialect_purity_score for mc in metric_cards]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Create histogram
    ax.hist(dialect_purity, bins="auto", alpha=0.7, color="darkgreen", edgecolor="black")
    
    # Add mean and std
    mean_purity = np.mean(dialect_purity)
    std_purity = np.std(dialect_purity)
    
    ax.axvline(float(mean_purity), color="red", linestyle="--", linewidth=2, label=f"Mean: {mean_purity:.4f}")
    ax.axvline(float(mean_purity + std_purity), color="orange", linestyle=":", linewidth=1, alpha=0.7)
    ax.axvline(float(mean_purity - std_purity), color="orange", linestyle=":", linewidth=1, alpha=0.7)
    
    ax.set_xlabel("Dialect Purity Score", fontsize=12)
    ax.set_ylabel("Frequency", fontsize=12)
    ax.set_title("Distribution of Dialect Purity Scores")
    if ax.get_legend_handles_labels()[0]:
        ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xlim((0, 1.05))

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return str(output_path)

    return None


def plot_anomalies(
    metric_cards: list[TextMetricCard],
    baseline_stats: CorpusBaselineStatistics,
    metric_name: str,
    threshold: float = 2.0,
    output_file: Optional[str] = None,
) -> Optional[str]:
    """Plot z-scores highlighting anomalies.
    
    Args:
        metric_cards: List of metric cards to check
        baseline_stats: Baseline statistics for comparison
        metric_name: Metric to analyze
        threshold: Z-score threshold for anomalies (default 2.0)
        output_file: Output file path (optional)
    
    Returns:
        Path to saved image or None if matplotlib not available
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore[reportUnknownReturnType]
    except ImportError:
        warnings.warn("matplotlib not installed; skipping visualization")
        return None

    baseline_metric_stats = _get_metric_stats(baseline_stats, metric_name)
    if not baseline_metric_stats:
        warnings.warn(f"No baseline stats for metric: {metric_name}")
        return None

    values = _extract_metric_values(metric_cards, metric_name)
    if not values:
        warnings.warn(f"No values found for metric: {metric_name}")
        return None

    # Compute z-scores
    z_scores = [baseline_metric_stats.normalize(v) for v in values]
    
    # Classify as normal or anomaly
    is_anomaly = [abs(z) > threshold for z in z_scores]
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot z-scores
    colors = ["red" if anomaly else "steelblue" for anomaly in is_anomaly]
    ax.scatter(range(len(z_scores)), z_scores, c=colors, alpha=0.6, s=50)
    
    # Add threshold lines
    ax.axhline(threshold, color="red", linestyle="--", linewidth=1, alpha=0.5, label=f"Threshold: ±{threshold}σ")
    ax.axhline(-threshold, color="red", linestyle="--", linewidth=1, alpha=0.5)
    ax.axhline(0, color="black", linestyle="-", linewidth=0.5, alpha=0.3)
    
    ax.set_xlabel("Text Index", fontsize=12)
    ax.set_ylabel("Z-Score", fontsize=12)
    ax.set_title(f"Z-Scores for {metric_name} (Anomalies in Red)")
    if ax.get_legend_handles_labels()[0]:
        ax.legend()
    ax.grid(True, alpha=0.3)

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return str(output_path)

    return None


def generate_analysis_report(
    metric_cards: list[TextMetricCard],
    baseline_stats: Optional[CorpusBaselineStatistics] = None,
    output_file: Optional[str] = None,
) -> dict:
    """Generate comprehensive statistical analysis report.
    
    Args:
        metric_cards: List of metric cards to analyze
        baseline_stats: Baseline statistics (optional)
        output_file: Output file path (optional)
    
    Returns:
        Dictionary containing analysis results
    """
    report = {
        "num_texts": len(metric_cards),
        "total_tokens": sum(mc.text_length for mc in metric_cards),
        "avg_tokens_per_text": _safe_mean([mc.text_length for mc in metric_cards]),
        # Quality analysis
        "quality": {
            "mean_dialect_purity": float(_safe_mean([mc.quality_flags.dialect_purity_score for mc in metric_cards])),
            "std_dialect_purity": float(np.nanstd([mc.quality_flags.dialect_purity_score for mc in metric_cards]) if metric_cards else 0.0),
            "texts_with_issues": len([mc for mc in metric_cards if mc.quality_flags.potential_issues]),
            "total_issues": sum(len(mc.quality_flags.potential_issues) for mc in metric_cards),
        },
        # Lexical analysis
        "lexical": {
            "mean_ttr": float(_safe_mean([mc.lexical.ttr for mc in metric_cards])),
            "std_ttr": float(np.nanstd([mc.lexical.ttr for mc in metric_cards]) if metric_cards else 0.0),
            "mean_yule_k": float(_safe_mean([mc.lexical.yule_k for mc in metric_cards if mc.lexical.yule_k])),
        },
        # Syntactic analysis
        "syntactic": {
            "mean_asl": float(_safe_mean([mc.syntactic.avg_sentence_length for mc in metric_cards])),
            "mean_clauses_per_sentence": float(_safe_mean([mc.syntactic.clauses_per_sentence for mc in metric_cards])),
        },
        # Contamination analysis
        "contamination": {
            "texts_with_eastern_forms": len([mc for mc in metric_cards if mc.contamination.code_switching_index > 0]),
            "mean_code_switching_index": float(_safe_mean([mc.contamination.code_switching_index for mc in metric_cards])),
        },
    }

    if baseline_stats:
        # Add baseline comparison
        report["baseline_comparison"] = _compare_to_baseline(metric_cards, baseline_stats)

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    return report


def _safe_mean(arr: list[float]) -> float:
    """Return mean of array; 0.0 if empty to avoid NumPy empty-slice warning."""
    if not arr:
        return 0.0
    return float(np.nanmean(arr))


def _extract_metric_values(
    metric_cards: list[TextMetricCard],
    metric_name: str,
) -> list[float]:
    """Extract values for a specific metric from metric cards.
    
    Args:
        metric_cards: List of metric cards
        metric_name: Name of metric (e.g., "lexical_ttr")
    
    Returns:
        List of metric values
    """
    values = []
    
    for mc in metric_cards:
        parts = metric_name.split("_", 1)
        if len(parts) != 2:
            continue
        
        category, sub_metric = parts
        
        try:
            if category == "lexical":
                val = getattr(mc.lexical, sub_metric)
            elif category == "syntactic":
                val = getattr(mc.syntactic, sub_metric)
            elif category == "morphological":
                val = getattr(mc.morphological, sub_metric)
            elif category == "quality":
                val = getattr(mc.quality_flags, sub_metric)
            elif category == "contamination":
                val = getattr(mc.contamination, sub_metric)
            else:
                continue
            
            if val is not None:
                values.append(float(val))
        except (AttributeError, ValueError):
            continue
    
    return values


def _get_metric_stats(
    baseline_stats: CorpusBaselineStatistics,
    metric_name: str,
) -> Optional[MetricStatistics]:
    """Get MetricStatistics for a specific metric from baseline.
    
    Args:
        baseline_stats: Baseline statistics
        metric_name: Name of metric
    
    Returns:
        MetricStatistics or None if not found
    """
    try:
        return getattr(baseline_stats, metric_name)
    except AttributeError:
        return None


def _compare_to_baseline(
    metric_cards: list[TextMetricCard],
    baseline_stats: CorpusBaselineStatistics,
) -> dict:
    """Compare metrics to baseline statistics.
    
    Args:
        metric_cards: Text metrics to compare
        baseline_stats: Baseline statistics
    
    Returns:
        Comparison report
    """
    comparison = {}
    
    # Check each metric
    metrics_to_check = [
        "lexical_ttr",
        "syntactic_asl",
        "quality_dialect_purity",
        "contamination_code_switching",
    ]
    
    for metric in metrics_to_check:
        baseline_metric = _get_metric_stats(baseline_stats, metric)
        if not baseline_metric:
            continue
        
        values = _extract_metric_values(metric_cards, metric)
        if not values:
            continue
        
        mean_val = _safe_mean(values)
        z_score = baseline_metric.normalize(float(mean_val))
        
        comparison[metric] = {
            "baseline_mean": round(baseline_metric.mean, 6),
            "text_mean": round(float(mean_val), 6),
            "z_score": round(float(z_score), 2),
            "is_anomalous": baseline_metric.is_anomaly(float(mean_val), threshold=2.0),
        }
    
    return comparison
