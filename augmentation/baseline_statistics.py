"""
Compute corpus baseline statistics for all metrics.

Establishes baseline statistics (mean, std dev, min, max, percentiles) for
metrics computed across real Western Armenian corpus texts. Used for:

1. Anomaly detection: Flag texts deviating >2σ from baseline
2. Quality scoring: Normalize quality scores relative to corpus
3. Trend analysis: Compare augmented text metrics to baseline distribution

Statistics are saved to cache/wa_metric_baseline_stats.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

import numpy as np

from linguistics.metrics.text_metrics import (
    QuantitativeLinguisticsAnalyzer,
    TextMetricCard,
)


@dataclass
class MetricStatistics:
    """Statistics for a single metric across corpus."""
    metric_name: str
    count: int
    mean: float
    std_dev: float
    min_value: float
    max_value: float
    median: float
    p25: float  # 25th percentile
    p75: float  # 75th percentile
    
    def is_anomaly(self, value: float, threshold: float = 2.0) -> bool:
        """Check if value is anomalous (>threshold std devs from mean).
        
        Args:
            value: Value to check
            threshold: Number of standard deviations (default 2.0)
        
        Returns:
            True if |value - mean| > threshold * std_dev
        """
        if self.std_dev == 0:
            return abs(value - self.mean) > 0
        return abs(value - self.mean) > threshold * self.std_dev
    
    def normalize(self, value: float) -> float:
        """Normalize value to z-score (standard deviations from mean).
        
        Args:
            value: Raw metric value
        
        Returns:
            Z-score: (value - mean) / std_dev
        """
        if self.std_dev == 0:
            return 0.0
        return (value - self.mean) / self.std_dev
    
    def percentile_rank(self, value: float) -> float:
        """Estimate percentile rank (0-100) for value.
        
        Args:
            value: Value to rank
        
        Returns:
            Percentile rank (0-100)
        """
        if value <= self.min_value:
            return 0.0
        if value >= self.max_value:
            return 100.0
        
        # Simple linear interpolation
        range_val = self.max_value - self.min_value
        if range_val == 0:
            return 50.0
        return ((value - self.min_value) / range_val) * 100


@dataclass
class CorpusBaselineStatistics:
    """Complete baseline statistics for all metrics."""
    compute_date: str
    num_texts: int
    total_tokens: int
    
    # Lexical metrics
    lexical_ttr: Optional[MetricStatistics] = None
    lexical_sttr: Optional[MetricStatistics] = None
    lexical_yule_k: Optional[MetricStatistics] = None

    # Syntactic metrics
    syntactic_asl: Optional[MetricStatistics] = None
    syntactic_clauses_per_sent: Optional[MetricStatistics] = None
    syntactic_flesch_kincaid: Optional[MetricStatistics] = None

    # Morphological metrics
    morph_em_freq: Optional[MetricStatistics] = None
    morph_im_freq: Optional[MetricStatistics] = None

    # Contamination metrics
    contamination_code_switching: Optional[MetricStatistics] = None

    # Quality metrics
    quality_dialect_purity: Optional[MetricStatistics] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "compute_date": self.compute_date,
            "num_texts": self.num_texts,
            "total_tokens": self.total_tokens,
        }
        
        for key, value in self.__dict__.items():
            if key not in ["compute_date", "num_texts", "total_tokens"] and value is not None:
                result[key] = asdict(value)
        
        return result


class CorpusBaselineComputer:
    """Compute baseline statistics from corpus texts."""

    def __init__(
        self,
        analyzer: Optional[QuantitativeLinguisticsAnalyzer] = None,
    ):
        """Initialize computer.
        
        Args:
            analyzer: QuantitativeLinguisticsAnalyzer instance
        """
        self.analyzer = analyzer or QuantitativeLinguisticsAnalyzer()

    def compute_from_metric_cards(
        self,
        metric_cards: list[TextMetricCard],
    ) -> CorpusBaselineStatistics:
        """Compute baseline statistics from existing metric cards.
        
        Args:
            metric_cards: List of metric cards from corpus texts
        
        Returns:
            CorpusBaselineStatistics with computed statistics
        """
        from datetime import datetime
        
        if not metric_cards:
            raise ValueError("No metric cards provided")

        # Extract metric values
        ttr_values = [mc.lexical.ttr for mc in metric_cards]
        sttr_values = [mc.lexical.sttr for mc in metric_cards]
        yule_k_values = [mc.lexical.yule_k for mc in metric_cards if mc.lexical.yule_k is not None]
        
        asl_values = [mc.syntactic.avg_sentence_length for mc in metric_cards]
        clauses_values = [mc.syntactic.clauses_per_sentence for mc in metric_cards]
        flesch_values = [mc.syntactic.flesch_kincaid_grade for mc in metric_cards]
        
        em_freq_values = [mc.morphological.suffix_em_frequency for mc in metric_cards]
        im_freq_values = [mc.morphological.suffix_im_frequency for mc in metric_cards]
        
        code_switching_values = [mc.contamination.code_switching_index for mc in metric_cards]
        
        dialect_purity_values = [mc.quality_flags.dialect_purity_score for mc in metric_cards]
        
        # Compute statistics
        return CorpusBaselineStatistics(
            compute_date=datetime.now().isoformat(),
            num_texts=len(metric_cards),
            total_tokens=sum(mc.text_length for mc in metric_cards),
            
            lexical_ttr=self._compute_stats("lexical_ttr", ttr_values),
            lexical_sttr=self._compute_stats("lexical_sttr", sttr_values),
            lexical_yule_k=self._compute_stats("lexical_yule_k", yule_k_values),
            
            syntactic_asl=self._compute_stats("syntactic_asl", asl_values),
            syntactic_clauses_per_sent=self._compute_stats("syntactic_clauses_per_sent", clauses_values),
            syntactic_flesch_kincaid=self._compute_stats("syntactic_flesch_kincaid", flesch_values),
            
            morph_em_freq=self._compute_stats("morph_em_freq", em_freq_values),
            morph_im_freq=self._compute_stats("morph_im_freq", im_freq_values),
            
            contamination_code_switching=self._compute_stats("contamination_code_switching", code_switching_values),
            
            quality_dialect_purity=self._compute_stats("quality_dialect_purity", dialect_purity_values),
        )

    def compute_from_texts(
        self,
        texts: list[str],
    ) -> CorpusBaselineStatistics:
        """Compute baseline statistics by analyzing corpus texts.
        
        Args:
            texts: List of corpus texts to analyze
        
        Returns:
            CorpusBaselineStatistics with computed statistics
        """
        if not texts:
            raise ValueError("No texts provided")

        print(f"Computing metrics for {len(texts)} corpus texts...")
        metric_cards = [
            self.analyzer.analyze_text(text, text_id=f"corpus_{i}", source="corpus")
            for i, text in enumerate(texts)
        ]
        print(f"✓ Computed metrics for {len(metric_cards)} texts")

        return self.compute_from_metric_cards(metric_cards)

    def _compute_stats(
        self,
        metric_name: str,
        values: list[float],
    ) -> MetricStatistics:
        """Compute statistics for a single metric.
        
        Args:
            metric_name: Name of metric
            values: List of metric values
        
        Returns:
            MetricStatistics with computed statistics
        """
        if not values:
            return MetricStatistics(
                metric_name=metric_name,
                count=0,
                mean=0.0,
                std_dev=0.0,
                min_value=0.0,
                max_value=0.0,
                median=0.0,
                p25=0.0,
                p75=0.0,
            )

        arr = np.array(values)
        
        return MetricStatistics(
            metric_name=metric_name,
            count=len(values),
            mean=float(np.mean(arr)),
            std_dev=float(np.std(arr)),
            min_value=float(np.min(arr)),
            max_value=float(np.max(arr)),
            median=float(np.median(arr)),
            p25=float(np.percentile(arr, 25)),
            p75=float(np.percentile(arr, 75)),
        )

    def save_statistics(
        self,
        stats: CorpusBaselineStatistics,
        output_file: str = "cache/wa_metric_baseline_stats.json",
    ) -> Path:
        """Save statistics to JSON file.
        
        Args:
            stats: CorpusBaselineStatistics to save
            output_file: Output file path
        
        Returns:
            Path to saved file
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(stats.to_dict(), f, ensure_ascii=False, indent=2)

        return output_path

    def load_statistics(
        self,
        input_file: str = "cache/wa_metric_baseline_stats.json",
    ) -> Optional[CorpusBaselineStatistics]:
        """Load statistics from JSON file.
        
        Args:
            input_file: Input file path
        
        Returns:
            CorpusBaselineStatistics or None if file doesn't exist
        """
        input_path = Path(input_file)
        
        if not input_path.exists():
            return None

        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Reconstruct MetricStatistics objects
        stats = CorpusBaselineStatistics(
            compute_date=data["compute_date"],
            num_texts=data["num_texts"],
            total_tokens=data["total_tokens"],
        )

        # Reconstruct each metric's statistics
        metric_fields = [
            "lexical_ttr",
            "lexical_sttr",
            "lexical_yule_k",
            "syntactic_asl",
            "syntactic_clauses_per_sent",
            "syntactic_flesch_kincaid",
            "morph_em_freq",
            "morph_im_freq",
            "contamination_code_switching",
            "quality_dialect_purity",
        ]

        for field_name in metric_fields:
            if field_name in data:
                metric_data = data[field_name]
                setattr(stats, field_name, MetricStatistics(**metric_data))

        return stats


def _read_texts_from_dirs(dirs: list[str], max_files: int = 5000) -> list[str]:
    """Read texts from directories of .txt files."""
    import random
    files: list[Path] = []
    for d in dirs:
        p = Path(d)
        if not p.exists():
            continue
        files.extend(sorted(p.rglob("*.txt")))
    if len(files) > max_files:
        random.Random(42).shuffle(files)
        files = files[:max_files]
    texts = []
    for f in files:
        try:
            texts.append(f.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
    return texts


def _load_texts_from_mongodb(config: dict, dialect: str | None = None, limit: int = 5000) -> list[str]:
    """Load document texts from MongoDB, optionally filtered by dialect."""
    try:
        from integrations.database.mongodb_client import MongoDBCorpusClient
    except ImportError:
        raise ImportError("MongoDB support requires: pip install pymongo")
    uri = config.get("database", {}).get("mongodb_uri", "mongodb://localhost:27017/")
    db = config.get("database", {}).get("mongodb_database", "western_armenian_corpus")
    with MongoDBCorpusClient(uri=uri, database_name=db) as client:
        query = {}
        if dialect:
            query["$or"] = [{"metadata.source_language_code": dialect}, {"metadata.language_code": dialect}]
        cursor = client.documents.find(query, {"text": 1}).limit(limit)
        return [doc["text"] for doc in cursor if doc.get("text")]


if __name__ == "__main__":
    import argparse
    import yaml

    parser = argparse.ArgumentParser(
        prog="python -m augmentation.baseline_statistics",
        description="Compute corpus baseline statistics for WA and/or EA.",
    )
    parser.add_argument("--wa-dirs", nargs="*", help="Directories with Western Armenian .txt files")
    parser.add_argument("--ea-dirs", nargs="*", help="Directories with Eastern Armenian .txt files")
    parser.add_argument("--mongodb", action="store_true", help="Load from MongoDB instead of dirs")
    parser.add_argument("--config", type=Path, default=Path("config/settings.yaml"), help="Config YAML")
    parser.add_argument("--output-wa", default="cache/wa_metric_baseline_stats.json", help="Output for WA baseline")
    parser.add_argument("--output-ea", default="cache/ea_metric_baseline_stats.json", help="Output for EA baseline")
    parser.add_argument("--limit", type=int, default=5000, help="Max documents per dialect")
    args = parser.parse_args()

    cfg = {}
    if args.config.exists():
        with open(args.config, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    computer = CorpusBaselineComputer()

    if args.mongodb:
        wa_texts = _load_texts_from_mongodb(cfg, dialect="hyw", limit=args.limit)
        ea_texts = _load_texts_from_mongodb(cfg, dialect="hy", limit=args.limit)
    else:
        wa_texts = _read_texts_from_dirs(args.wa_dirs or [], max_files=args.limit) if args.wa_dirs else []
        ea_texts = _read_texts_from_dirs(args.ea_dirs or [], max_files=args.limit) if args.ea_dirs else []

    if not wa_texts and not ea_texts:
        # Fallback: Example from sample corpus texts
        sample_texts = [
        "Ես բերիմ տուն մեծ և գեղավոր։ Այն տուն շատ հին էր և  լո այն ամեն մեկ կողմից գեղանկար ամպ ծածկել էր։",
        "Նա գալ է վաղ հետո ինձ տուն մեծ հետ գիր մեծ թե փոքր ունել թե չունել չի կարենալ ասել։",
        "Մենք բերիմ բան շատ կարևոր և բազմ ամեն մեկ անձ շատ շարժ եւ տեղավորել ընդամենը շատ մեծ տեղ ունի մहै।",
        "Նրանք գերել են ամբ բազմ տոկո ինձ հետ բերել ամ մեծ բարձր և շատ ցածր մերձ ստացել ամ լճ տեղ կուչա գ շատ կառուցվածք հետ զանց ինձ։",
        "Աղջիկ շատ կամ պետք ինձ հետ ասել բառ մեծ շատ հետ կամ պետք ունեղ չունեղ կամ պետք չունեղ ունեղ ասել թե չասել։",
        ]
        wa_texts = sample_texts
        print("No WA/EA dirs or MongoDB data; using sample texts.")

    if wa_texts:
        print(f"Computing WA baseline from {len(wa_texts)} texts...")
        wa_stats = computer.compute_from_texts(wa_texts)
        computer.save_statistics(wa_stats, args.output_wa)
        print(f"✓ Saved WA baseline to {args.output_wa}")
        if wa_stats.lexical_ttr:
            print(f"  Lexical TTR: {wa_stats.lexical_ttr.mean:.4f} ± {wa_stats.lexical_ttr.std_dev:.4f}")

    if ea_texts:
        print(f"Computing EA baseline from {len(ea_texts)} texts...")
        ea_stats = computer.compute_from_texts(ea_texts)
        computer.save_statistics(ea_stats, args.output_ea)
        print(f"✓ Saved EA baseline to {args.output_ea}")
        if ea_stats.lexical_ttr:
            print(f"  Lexical TTR: {ea_stats.lexical_ttr.mean:.4f} ± {ea_stats.lexical_ttr.std_dev:.4f}")
