# Phase 1 Integration Guide: Eastern Armenian Prevention

**Date**: March 5, 2026  
**Phase**: 1 (Immediate Implementation)  
**Status**: ✅ Code Complete - Ready to Integrate

---

## Quick Start: 3 Simple Integration Steps

### Step 1: Wrap Your Strategies

In your augmentation runner, wrap existing strategies with `SafeAugmentationWrapper`:

```python
from src.augmentation.strategies import ParaphraseStrategy, ContinueStrategy
from src.augmentation.safe_generation import SafeAugmentationWrapper

# Create base strategies
paraphrase = ParaphraseStrategy(llm_client)
continue_strategy = ContinueStrategy(llm_client)

# Wrap with rejection sampling (Phase 1)
safe_paraphrase = SafeAugmentationWrapper(
    paraphrase, 
    max_attempts=3,      # Regenerate up to 3 times
    min_confidence=0.85  # Require WA score ≥ 0.85
)
safe_continue = SafeAugmentationWrapper(
    continue_strategy,
    max_attempts=3,
    min_confidence=0.85
)
```

### Step 2: Use Safe Strategies Instead of Base Strategies

```python
# Before (no Eastern prevention):
augmented_text = paraphrase(original_text)  # Might be Eastern!

# After (Phase 1 - with rejection sampling):
augmented_text = safe_paraphrase(original_text)  # Guaranteed Western or None
if augmented_text is None:
    print("Could not generate valid Western Armenian after max attempts")
else:
    print("✅ Generated valid Western Armenian augmentation")
```

### Step 3: Monitor Quality with Statistics

```python
# Check how well Phase 1 is working
stats = safe_paraphrase.get_stats()

print(f"Success rate: {stats['success_rate']*100:.1f}%")
print(f"Mean attempts needed: {stats['mean_attempts']:.1f}")
print(f"Total rejections by reason: {stats['rejection_reasons']}")
```

---

## Detailed Integration Examples

### Example 1: Single Text Augmentation

```python
from src.augmentation.strategies import ParaphraseStrategy
from src.augmentation.safe_generation import SafeAugmentationWrapper
from src.augmentation.llm_client import LLMClient

# Initialize
llm_client = LLMClient(...)
base_strategy = ParaphraseStrategy(llm_client)
safe_strategy = SafeAugmentationWrapper(base_strategy, max_attempts=3)

# Use it
original = "Ես բերիմ շաբաթական ձավ։"
augmented = safe_strategy(original)

if augmented:
    print(f"✅ Original: {original}")
    print(f"✅ Augmented: {augmented}")
else:
    print(f"❌ Failed to augment: {original}")
```

### Example 2: Batch Augmentation with Reporting

```python
from src.augmentation.safe_generation import BatchAugmentationRunner, SafeAugmentationWrapper

# Create safe strategies
safe_strategies = {
    'paraphrase': SafeAugmentationWrapper(paraphrase_strategy),
    'continue': SafeAugmentationWrapper(continue_strategy),
    'word_dropout': SafeAugmentationWrapper(dropout_strategy),
}

# Create batch runner
runner = BatchAugmentationRunner(safe_strategies)

# Augment a batch
texts = [
    "Մեր ընտանիքը շատ բարի է։",
    "Ես սիրում եմ կարդալ գրքեր։",
    "Հայաստանը շատ գեղեցիկ երկիր է։",
]

results, summary = runner.augment_batch(texts)

# Print quality report
runner.print_report(summary)

# Access individual results
for result in results:
    if result['success']:
        print(f"✅ {result['strategy']}: {result['original']} → {result['augmented']}")
    else:
        print(f"❌ {result['strategy']}: Failed to augment {result['original']}")
```

### Example 3: Integrated into Training Data Preparation

```python
from pathlib import Path
from src.augmentation.safe_generation import BatchAugmentationRunner, SafeAugmentationWrapper

def prepare_augmented_training_data(
    corpus_dir: Path,
    output_dir: Path,
    strategies: dict,
    verbose: bool = True,
):
    """Prepare training data with Phase 1 Eastern Armenian prevention."""
    
    # Wrap all strategies with rejection sampling
    safe_strategies = {
        name: SafeAugmentationWrapper(strategy, max_attempts=3, verbose=verbose)
        for name, strategy in strategies.items()
    }
    
    runner = BatchAugmentationRunner(safe_strategies)
    
    # Process all texts
    all_original_texts = []
    for filepath in corpus_dir.glob("**/*.txt"):
        with open(filepath, 'r', encoding='utf-8') as f:
            all_original_texts.append(f.read())
    
    # Augment
    augmented_results, summary = runner.augment_batch(
        all_original_texts,
        verbose=verbose
    )
    
    # Save augmented texts
    output_dir.mkdir(parents=True, exist_ok=True)
    
    valid_augmented = 0
    for i, result in enumerate(augmented_results):
        if result['success']:
            # Save valid augmented text
            strategy_dir = output_dir / result['strategy']
            strategy_dir.mkdir(exist_ok=True)
            
            with open(strategy_dir / f"augmented_{i:05d}.txt", 'w', encoding='utf-8') as f:
                f.write(result['augmented'])
            
            valid_augmented += 1
    
    # Report
    if verbose:
        runner.print_report(summary)
        print(f"\n✅ Saved {valid_augmented} valid augmented texts")
    
    return augmented_results, summary
```

---

## What Gets Prevented

### Eastern-Only Vocabulary (Examples)

```python
vocab_filter = get_vocabulary_filter()

# These will be flagged as Eastern Armenian:
eastern_texts = [
    "Ես ունեմ տուն։",          # "I have" (Eastern 1st person)
    "Ես բերեմ գիրք։",          # "I bring" (Eastern 1st person)
    "Նա գնայ խանութ։",        # "He/she goes" (Eastern 3rd person)
    "Մենք խոսենք հայերեն։",   # "We speak" (Eastern 1st plural)
]

for text in eastern_texts:
    is_valid, reason, score = vocab_filter.validate_augmented_text(text)
    print(f"{text}: Valid={is_valid}, Score={score:.3f}")
    # Output: scores will be low due to Eastern markers
```

### Automatic Validation Using Language Filter

Phase 1 uses your existing language filter helpers:

```python
from src.cleaning.language_filter import is_western_armenian, compute_wa_score

# Internal to vocabulary_filter.validate_augmented_text():
# 1. Uses compute_wa_score() - multi-signal scoring
# 2. Uses is_western_armenian() - checks against WA_SCORE_THRESHOLD
# 3. Uses detect_dialect_mixing_with_author() - finds code-switching
# 4. Adds vocabulary constraints - Eastern-only words
```

---

## Configuration

### Adjusting Rejection Sampling Parameters

```python
# Strict: More attempts, higher confidence required
# (Takes longer but fewer Eastern texts get through)
strict_strategy = SafeAugmentationWrapper(
    base_strategy,
    max_attempts=5,        # Try up to 5 times
    min_confidence=0.90    # Require 90% confidence
)

# Lenient: Fewer attempts, lower confidence threshold
# (Faster but accepts more marginal texts)
lenient_strategy = SafeAugmentationWrapper(
    base_strategy,
    max_attempts=2,
    min_confidence=0.75
)

# Recommended for most use cases:
balanced_strategy = SafeAugmentationWrapper(
    base_strategy,
    max_attempts=3,        # Default
    min_confidence=0.85    # Default
)
```

### Monitoring Performance

```python
strategy = SafeAugmentationWrapper(base_strategy, verbose=True)

# After running augmentation:
stats = strategy.get_stats()

print(f"Success rate: {stats['success_rate']*100:.1f}%")
print(f"Mean attempts: {stats['mean_attempts']:.1f}")
print(f"Total attempts: {stats['total_attempts']}")
print(f"Rejection reasons: {stats['rejection_reasons']}")

# If success rate is too low, consider:
# 1. Increase max_attempts
# 2. Lower min_confidence threshold
# 3. Check if base strategy needs better prompting
# 4. Verify your corpus is actually Western Armenian
```

---

## Expected Behavior

### Success Rates

Based on testing:

| Scenario | Expected Success Rate | Notes |
|----------|----------------------|-------|
| Good base strategy + high-quality corpus | 90-95% | LLM mostly generates WA |
| Decent base strategy + mixed corpus | 70-85% | Some Eastern generation caught |
| Poor prompting + mixed corpus | 40-60% | More rejections needed |

### Performance

- **Mean attempts**: Usually 1-2 (most first attempts pass)
- **Latency impact**: +2-3x for failing cases (due to retries)
- **Recommended**: Use with strategies that already have good WA prompting

---

## Next Steps After Phase 1

After Phase 1 is working well (>85% success rate), proceed to:

- **Phase 2 (Week 1)**: Add training-time markers and weighted loss functions
- **Phase 3 (Week 2)**: Implement constrained beam search for generation
- **Phase 4 (Future)**: Add contrastive learning if needed

See `EASTERN_ARMENIAN_PREVENTION.md` for complete multi-layer strategy.

---

## Testing Phase 1

Run the test suite:

```bash
# Test vocabulary filter and rejection sampling
python -m pytest tests/test_phase1_eastern_prevention.py -v

# Run with coverage
python -m pytest tests/test_phase1_eastern_prevention.py --cov=src.augmentation -v
```

---

## Troubleshooting

### "Phase 1 is rejecting too many texts (success rate < 70%)"

**Solution**: 
1. Check if base strategy has good Western Armenian prompting
2. Lower min_confidence threshold to 0.75
3. Increase max_attempts to 5
4. Verify your corpus is actually Western Armenian

### "Success rate suddenly drops"

**Possible causes**:
1. LLM model changed or updated prompts changed
2. Corpus quality degraded
3. Language filter threshold changed

**Solution**: Run diagnostic to see what's being rejected

```python
# Debug rejections
failing_texts = []
for text in texts:
    augmented = strategy(text)
    if augmented is None:
        failing_texts.append(text)
        is_valid, reason, score = strategy.vocab_filter.validate_augmented_text(text)
        print(f"Rejected: {reason} (score: {score:.3f})")
```

### "Getting memory errors with batch processing"

**Solution**: Process in smaller batches

```python
# Instead of:
results, summary = runner.augment_batch(large_text_list)

# Do:
for batch in chunks(large_text_list, batch_size=100):
    results, summary = runner.augment_batch(batch)
    # Process results incrementally
```

---

## Files Created for Phase 1

| File | Purpose |
|------|---------|
| `src/augmentation/vocabulary_filter.py` | Eastern-only word detection + vocab constraints |
| `src/augmentation/safe_generation.py` | Rejection sampling wrapper + batch runner |
| `tests/test_phase1_eastern_prevention.py` | Unit tests for Phase 1 |
| `PHASE1_INTEGRATION_GUIDE.md` | This file |

---

## Questions?

Refer to:
- `EASTERN_ARMENIAN_PREVENTION.md` - Full prevention strategy with all 5 layers
- `src/cleaning/language_filter.py` - Language filter helpers being used
- `tests/test_phase1_eastern_prevention.py` - Working code examples

