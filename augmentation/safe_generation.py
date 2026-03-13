"""Phase 1: Rejection Sampling for Western Armenian Generation

Implements safe augmentation with guaranteed Western Armenian output.
Uses rejection sampling: keep regenerating until we get valid Western Armenian.

This is the quick-start Phase 1 implementation that requires minimal
changes to existing code.
"""

from __future__ import annotations

import logging
from typing import Optional

from linguistics.metrics import validate_augmentation_output

logger = logging.getLogger(__name__)


class SafeAugmentationWrapper:
    """
    Wraps any augmentation strategy with rejection sampling.
    
    Guarantees input returns Western Armenian text or None.
    Delegates validation to validate_augmentation_output.
    
    Usage:
        strategy = ParaphraseStrategy(llm_client)
        safe_strategy = SafeAugmentationWrapper(strategy, max_attempts=5)
        result = safe_strategy(original_text)  # None if all attempts failed
    """

    @property
    def name(self) -> str:
        """Strategy name for batch_worker strat_map."""
        return getattr(self.base_strategy, "name", "unknown")

    def __init__(
        self,
        base_strategy,
        max_attempts: int = 3,
        min_confidence: float = 0.85,
        verbose: bool = False,
    ):
        """
        Args:
            base_strategy: The underlying augmentation strategy (ParaphraseStrategy, etc.)
            max_attempts: Max regeneration attempts before giving up
            min_confidence: Min WA score (0-1) to accept output
            verbose: Whether to log rejection details
        """
        self.base_strategy = base_strategy
        self.max_attempts = max_attempts
        self.min_confidence = min_confidence
        self.verbose = verbose
        
        # Statistics tracking
        self.stats = {
            'total_calls': 0,
            'successful': 0,
            'failed': 0,
            'total_attempts': 0,
            'rejection_reasons': {},
        }
    
    def __call__(self, text: str) -> Optional[str]:
        """
        Apply augmentation strategy with rejection sampling.
        
        Args:
            text: Original text to augment
        
        Returns:
            Augmented text guaranteed to be Western Armenian, or None if all attempts failed
        """
        self.stats['total_calls'] += 1
        
        for attempt in range(self.max_attempts):
            self.stats['total_attempts'] += 1
            
            # Generate
            generated = self.base_strategy(text)
            
            if generated is None:
                if self.verbose:
                    logger.debug(f"Attempt {attempt + 1}: Strategy returned None")
                continue
            
            # Validate via validate_augmentation_output (single source of truth)
            validation = validate_augmentation_output(generated, threshold=self.min_confidence)
            is_valid = validation.passed and validation.wa_score >= self.min_confidence
            reason = validation.feedback if not validation.passed else ""
            wa_score = validation.wa_score
            
            if is_valid:
                # Success!
                if self.verbose and attempt > 0:
                    logger.info(
                        f"✅ {self.base_strategy.name}: Generated valid WA after "
                        f"{attempt + 1} attempts (score: {wa_score:.3f})"
                    )
                self.stats['successful'] += 1
                return generated
            else:
                # Rejection
                if self.verbose:
                    logger.debug(
                        f"Attempt {attempt + 1}: Rejected - {reason or 'validation failed'} (score: {wa_score:.3f})"
                    )
                # Track rejection reason
                reason_key = (reason or "validation_failed").split(":")[0] if ":" in (reason or "") else (reason or "validation_failed")
                self.stats['rejection_reasons'][reason_key] = \
                    self.stats['rejection_reasons'].get(reason_key, 0) + 1
        
        # All attempts exhausted
        self.stats['failed'] += 1
        if self.verbose:
            logger.warning(
                f"⚠️ {self.base_strategy.name}: Failed to generate valid WA "
                f"after {self.max_attempts} attempts"
            )
        
        return None
    
    def get_stats(self) -> dict:
        """Get statistics about rejection sampling performance."""
        return {
            **self.stats,
            'success_rate': self.stats['successful'] / self.stats['total_calls']
            if self.stats['total_calls'] > 0 else 0.0,
            'mean_attempts': self.stats['total_attempts'] / self.stats['total_calls']
            if self.stats['total_calls'] > 0 else 0.0,
        }
    
    def reset_stats(self):
        """Reset performance statistics."""
        self.stats = {
            'total_calls': 0,
            'successful': 0,
            'failed': 0,
            'total_attempts': 0,
            'rejection_reasons': {},
        }


class BatchAugmentationRunner:
    """
    Applies safe augmentation to a batch of texts.
    
    Tracks quality metrics and provides summary report.
    """
    
    def __init__(self, strategies: dict[str, SafeAugmentationWrapper]):
        """
        Args:
            strategies: Dict mapping strategy names to SafeAugmentationWrapper instances
        """
        self.strategies = strategies
    
    def augment_batch(
        self,
        texts: list[str],
        strategy_name: str | None = None,
        verbose: bool = False,
    ) -> tuple[list[dict], dict]:
        """
        Apply augmentation to batch of texts.
        
        Args:
            texts: List of texts to augment
            strategy_name: Specific strategy to use, or None to use all
            verbose: Whether to log detailed info
        
        Returns:
            (augmented_results, summary_stats)
            
            augmented_results: List of dicts with keys:
            - original: original text
            - augmented: augmented text (or None if failed)
            - strategy: strategy name used
            - success: whether augmentation succeeded
            
            summary_stats: Dict with overall quality metrics
        """
        strategies_to_use = {
            strategy_name: self.strategies[strategy_name]
        } if strategy_name else self.strategies
        
        augmented_results = []
        overall_stats = {
            'total_texts': len(texts),
            'successful_augmentations': 0,
            'failed_augmentations': 0,
            'by_strategy': {},
        }
        
        for text in texts:
            for strat_name, safe_strategy in strategies_to_use.items():
                augmented = safe_strategy(text)
                
                success = augmented is not None
                if success:
                    overall_stats['successful_augmentations'] += 1
                else:
                    overall_stats['failed_augmentations'] += 1
                
                augmented_results.append({
                    'original': text,
                    'augmented': augmented,
                    'strategy': strat_name,
                    'success': success,
                })
                
                # Track stats per strategy
                if strat_name not in overall_stats['by_strategy']:
                    overall_stats['by_strategy'][strat_name] = {
                        'successful': 0,
                        'failed': 0,
                        'stats': safe_strategy.get_stats(),
                    }
                
                if success:
                    overall_stats['by_strategy'][strat_name]['successful'] += 1
                else:
                    overall_stats['by_strategy'][strat_name]['failed'] += 1
        
        # Add rates
        overall_stats['success_rate'] = \
            overall_stats['successful_augmentations'] / overall_stats['total_texts'] \
            if overall_stats['total_texts'] > 0 else 0.0
        
        return augmented_results, overall_stats
    
    def print_report(self, summary_stats: dict):
        """Pretty-print augmentation quality report."""
        print("\n" + "=" * 70)
        print("AUGMENTATION QUALITY REPORT (Phase 1: Rejection Sampling)")
        print("=" * 70)
        
        print(f"\nOverall Results:")
        print(f"  Total texts: {summary_stats['total_texts']}")
        print(f"  ✅ Successful: {summary_stats['successful_augmentations']}")
        print(f"  ❌ Failed: {summary_stats['failed_augmentations']}")
        print(f"  Success rate: {summary_stats['success_rate']*100:.1f}%")
        
        print(f"\nBy Strategy:")
        for strat_name, stats in summary_stats['by_strategy'].items():
            print(f"\n  {strat_name}:")
            print(f"    ✅ Successful: {stats['successful']}")
            print(f"    ❌ Failed: {stats['failed']}")
            print(f"    Mean attempts: {stats['stats']['mean_attempts']:.1f}")
            
            if stats['stats']['rejection_reasons']:
                print(f"    Top rejection reasons:")
                for reason, count in sorted(
                    stats['stats']['rejection_reasons'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:3]:
                    print(f"      - {reason}: {count}")

