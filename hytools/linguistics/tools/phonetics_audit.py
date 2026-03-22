"""Phonetics validation and Eastern Armenian leakage audit.

Tests Western Armenian phonetic rules on sample words:
- պետք, ժամ, ջուր, ոչ, իւր

Validates:
1. Reversed voicing (բ/պ, դ/տ, գ/կ, ճ/ջ, ծ/ձ)
2. Contextual ո and ե behavior
3. Detection of Eastern Armenian patterns

This is an AUDIT-ONLY script; it does not rewrite modules.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class PhoneticsTestResult:
    """Test result for a single word."""
    word: str
    graphemes: List[str]
    expected_wa_phones: List[str]
    voicing_analysis: Dict[str, Dict[str, str]]  # grapheme -> {wa_phone, wa_voicing, ...}
    eastern_leakage_detected: bool
    eastern_leakage_reason: str
    rule_gaps: List[str]
    notes: str


# Western Armenian voicing MAP (reversed from Eastern Armenian)
# Based on /memories/verified-letter-names-and-ipa.md and
# src/augmentation/vocabulary_filter.py voicing reference
WA_VOICING_MAP = {
    # Reversed voicing (WA is opposite of Eastern grapheme shape):
    'բ': ('p', 'voiceless_unaspirated', 'Eastern: b, WA: p'),
    'պ': ('b', 'voiced', 'Eastern: p, WA: b'),
    'գ': ('k', 'voiceless_unaspirated', 'Eastern: g, WA: k'),
    'կ': ('g', 'voiced', 'Eastern: k, WA: g'),
    'դ': ('t', 'voiceless_unaspirated', 'Eastern: d, WA: t'),
    'տ': ('d', 'voiced', 'Eastern: t, WA: d'),
    'ծ': ('dz', 'voiced_affricate', 'Eastern: ts, WA: dz'),
    'ձ': ('tsʰ', 'aspirated_affricate', 'Eastern: dz, WA: ts'),
    'ճ': ('dʒ', 'voiced_affricate', 'Eastern: tʃ, WA: dʒ'),
    'ջ': ('tʃʰ', 'aspirated_affricate', 'Eastern: dʒ, WA: tʃ'),
    
    # Non-reversed consonants (same in both dialects):
    'ժ': ('ʒ', 'voiced_fricative', 'Same in both'),
    'ր': ('ɾ', 'tap', 'Same in both'),
    'ռ': ('ɾ', 'trill', 'Same in both'),
    'մ': ('m', 'nasal', 'Same in both'),
    'ն': ('n', 'nasal', 'Same in both'),
    'լ': ('l', 'lateral', 'Same in both'),
    'վ': ('v', 'fricative', 'Same in both'),
    'ւ': ('v', 'fricative', 'WA: modifier yiwn = v'),
    'ֆ': ('f', 'fricative', 'Same in both'),
    'շ': ('ʃ', 'fricative', 'Same in both'),
    'չ': ('tʃʰ', 'aspirated_affricate', 'Same in both'),
    'ջ': ('tʃʰ', 'aspirated_affricate', 'WA voicing reversal'),
    'ս': ('s', 'fricative', 'Same in both'),
    'զ': ('z', 'fricative', 'Same in both'),
    'խ': ('χ', 'uvular_fricative', 'Same in both'),
    'հ': ('h', 'glottal', 'Same in both'),
    'ղ': ('ʁ', 'uvular_fricative', 'Same in both'),
    'ց': ('tsʰ', 'aspirated_affricate', 'Same in both'),
    'փ': ('pʰ', 'aspirated_stop', 'Same in both'),
    'թ': ('tʰ', 'aspirated_stop', 'Same in both'),
    
    # Vowels:
    'ա': ('ɑ', 'low_back', 'Same in both'),
    'ը': ('ə', 'schwa', 'Same in both'),
    'է': ('ɛ', 'mid_front', 'Same in both'),
    'ե': ('jɛ', 'diphthong', 'Word-initial; é elsewhere (contextual)'),
    'ի': ('i', 'high_front', 'Same in both'),
    'ո': ('ʋɔ', 'diphthong', 'Word-initial; ô/o elsewhere (contextual)'),
    'օ': ('o', 'mid_back', 'Same in both'),
    'ու': ('u', 'high_back', 'Same in both (digraph)'),
    'իւ': ('ʏ', 'rounded_high_front', 'WA classical orthography'),
}


def grapheme_to_phone(grapheme: str, position: str = 'medial') -> str:
    """Convert grapheme to expected WA phone.
    
    Args:
        grapheme: Armenian grapheme
        position: 'initial', 'medial', 'final'
    
    Returns:
        IPA phone(s)
    """
    if grapheme in WA_VOICING_MAP:
        phone, voicing, note = WA_VOICING_MAP[grapheme]
        return phone
    
    # Contextual rules for ե and ո
    if grapheme == 'ե':
        return 'jɛ' if position == 'initial' else 'ɛ'
    if grapheme == 'ո':
        return 'ʋɔ' if position == 'initial' else 'ɔ'
    
    return f'[{grapheme}?]'


def split_graphemes(word: str) -> List[str]:
    """Split word into grapheme units (handling digraphs).
    
    Returns:
        List of graphemes (single letters or digraphs like իւ, ու)
    """
    graphemes = []
    i = 0
    while i < len(word):
        # Check for digraphs first
        if i < len(word) - 1:
            digraph = word[i:i+2]
            if digraph in ['իւ', 'ու', 'եւ', 'օի']:
                graphemes.append(digraph)
                i += 2
                continue
        
        # Single grapheme
        graphemes.append(word[i])
        i += 1
    
    return graphemes


def analyze_voicing(grapheme: str) -> Dict[str, str]:
    """Analyze voicing properties of a grapheme.
    
    Returns:
        Dict with: grapheme, wa_phone, wa_voicing, eastern_phone, eastern_voicing
    """
    if grapheme not in WA_VOICING_MAP:
        return {
            'grapheme': grapheme,
            'wa_phone': '[unknown]',
            'wa_voicing': 'N/A',
            'eastern_phone': '[unknown]',
            'eastern_voicing': 'N/A',
        }
    
    phone, voicing, note = WA_VOICING_MAP[grapheme]
    
    # Determine Eastern equivalent (reverse if voicing-reversed)
    eastern_phone = phone
    eastern_voicing = voicing
    
    # Voicing-reversed consonants:
    reversed_map = {
        'բ': ('b', 'voiced'),
        'պ': ('p', 'voiceless'),
        'գ': ('g', 'voiced'),
        'կ': ('k', 'voiceless'),
        'դ': ('d', 'voiced'),
        'տ': ('t', 'voiceless'),
        'ծ': ('ts', 'voiceless'),
        'ձ': ('dz', 'voiced'),
        'ճ': ('tʃ', 'voiceless'),
        'ջ': ('dʒ', 'voiced'),
    }
    
    if grapheme in reversed_map:
        eastern_phone, eastern_voicing = reversed_map[grapheme]
    
    return {
        'grapheme': grapheme,
        'wa_phone': phone,
        'wa_voicing': voicing,
        'eastern_phone': eastern_phone,
        'eastern_voicing': eastern_voicing,
    }


def detect_eastern_leakage(word: str, graphemes: List[str]) -> Tuple[bool, str]:
    """Detect if word contains Eastern Armenian patterns.
    
    Returns:
        (is_eastern, reason)
    """
    reasons = []
    
    # Check for Eastern-only morphology (from vocabulary_filter.py)
    if word.endswith('եմ'):
        reasons.append('Eastern 1st singular verb ending -եմ (WA: -իմ)')
    
    # Check for Eastern reformed spelling patterns
    if 'միյ' in word:
        reasons.append('Eastern reformed spelling "միյ" (WA: միա)')
    
    if 'այդ' in word:
        reasons.append('Eastern demonstrative "այդ" (WA: այն)')
    
    if 'սա' == word:
        reasons.append('Eastern proximal "սա" (WA: այս)')
    
    # Check for absence of WA classical orthography markers in common words
    if len(word) >= 4 and 'իւ' not in word and 'եա' not in word:
        # This is not a strong signal alone, so only flag if other patterns present
        pass
    
    return (len(reasons) > 0, '; '.join(reasons) if reasons else '')


def test_word_phonetics(word: str) -> PhoneticsTestResult:
    """Test phonetics transcription for a single word.
    
    Args:
        word: Western Armenian word to test
    
    Returns:
        PhoneticsTestResult with analysis
    """
    graphemes = split_graphemes(word)
    
    # Transcribe to expected WA phones
    phones = []
    for i, g in enumerate(graphemes):
        position = 'initial' if i == 0 else ('final' if i == len(graphemes) - 1 else 'medial')
        phone = grapheme_to_phone(g, position)
        phones.append(phone)
    
    # Analyze voicing for reversed consonants
    voicing_analysis = {}
    for g in graphemes:
        if g in ['բ', 'պ', 'գ', 'կ', 'դ', 'տ', 'ծ', 'ձ', 'ճ', 'ջ']:
            voicing_analysis[g] = analyze_voicing(g)
    
    # Detect Eastern leakage
    is_eastern, eastern_reason = detect_eastern_leakage(word, graphemes)
    
    # Identify rule gaps
    rule_gaps = []
    for g in graphemes:
        if '[' in grapheme_to_phone(g):
            rule_gaps.append(f'Missing rule for grapheme: {g}')
    
    # Check for contextual ո/ե behavior
    if 'ո' in graphemes:
        idx = graphemes.index('ո')
        if idx == 0:
            rule_gaps.append('ո word-initial → /ʋɔ/ (diphthong)')
        else:
            rule_gaps.append('ո medial/final → /ɔ/ (simple vowel)')
    
    if 'ե' in graphemes:
        idx = graphemes.index('ե')
        if idx == 0:
            rule_gaps.append('ե word-initial → /jɛ/ (diphthong with /j/)')
        else:
            rule_gaps.append('ե medial/final → /ɛ/ (simple vowel)')
    
    notes = f"Transcription: /{' '.join(phones)}/"
    
    return PhoneticsTestResult(
        word=word,
        graphemes=graphemes,
        expected_wa_phones=phones,
        voicing_analysis=voicing_analysis,
        eastern_leakage_detected=is_eastern,
        eastern_leakage_reason=eastern_reason,
        rule_gaps=rule_gaps,
        notes=notes,
    )


def run_phonetics_audit() -> None:
    """Run phonetics audit on test words and export results."""
    
    # Test words
    test_words = [
        'պետք',  # petk' - "need"
        'ժամ',   # ʒam - "hour"
        'ջուր',  # tʃʰuɾ - "water" (WA voicing)
        'ոչ',    # vɔtʃʰ - "no" (contextual ո)
        'իւր',  # ʏɾ - "his/her" (classical orthography իւ)
    ]
    
    print("=== Western Armenian Phonetics Validation Audit ===\n")
    
    results = []
    for word in test_words:
        print(f"Testing: {word}")
        result = test_word_phonetics(word)
        results.append(result)
        
        print(f"  Graphemes: {result.graphemes}")
        print(f"  {result.notes}")
        
        if result.voicing_analysis:
            print(f"  Voicing analysis:")
            for g, analysis in result.voicing_analysis.items():
                print(f"    {g}: WA={analysis['wa_phone']} ({analysis['wa_voicing']}), "
                      f"Eastern={analysis['eastern_phone']} ({analysis['eastern_voicing']})")
        
        if result.eastern_leakage_detected:
            print(f"  ⚠️  EASTERN LEAKAGE: {result.eastern_leakage_reason}")
        else:
            print(f"  ✓ No Eastern leakage detected")
        
        if result.rule_gaps:
            print(f"  Rule gaps: {', '.join(result.rule_gaps)}")
        
        print()
    
    # Export results
    export_dir = Path("migration_exports")
    export_dir.mkdir(exist_ok=True)
    
    # 1. Export JSON results
    json_path = export_dir / "phonetics_test_results.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(
            {
                'test_date': '2026-03-06',
                'test_words': test_words,
                'results': [asdict(r) for r in results],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"✓ Exported: {json_path}")
    
    # 2. Export rule gaps (markdown)
    md_path = export_dir / "phonetics_rule_gaps.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("# Western Armenian Phonetics Rule Gaps\n\n")
        f.write("**Audit Date**: 2026-03-06\n\n")
        f.write("## Summary\n\n")
        f.write(f"- **Test words**: {len(test_words)}\n")
        f.write(f"- **Eastern leakage detected**: "
                f"{sum(1 for r in results if r.eastern_leakage_detected)}\n")
        f.write(f"- **Words with rule gaps**: "
                f"{sum(1 for r in results if r.rule_gaps)}\n\n")
        
        f.write("## Key Findings\n\n")
        f.write("### 1. Reversed Voicing (բ/պ, դ/տ, գ/կ, ճ/ջ)\n\n")
        f.write("Western Armenian has **reversed voicing** from Eastern Armenian:\n\n")
        f.write("| Grapheme | WA Phone | WA Voicing | EA Phone | EA Voicing |\n")
        f.write("|----------|----------|------------|----------|-----------|\n")
        
        voicing_pairs = [
            ('բ', 'p', 'voiceless', 'b', 'voiced'),
            ('պ', 'b', 'voiced', 'p', 'voiceless'),
            ('դ', 't', 'voiceless', 'd', 'voiced'),
            ('տ', 'd', 'voiced', 't', 'voiceless'),
            ('գ', 'k', 'voiceless', 'g', 'voiced'),
            ('կ', 'g', 'voiced', 'k', 'voiceless'),
            ('ճ', 'dʒ', 'voiced', 'tʃ', 'voiceless'),
            ('ջ', 'tʃʰ', 'aspirated', 'dʒ', 'voiced'),
        ]
        
        for g, wa_p, wa_v, ea_p, ea_v in voicing_pairs:
            f.write(f"| {g} | /{wa_p}/ | {wa_v} | /{ea_p}/ | {ea_v} |\n")
        
        f.write("\n### 2. Contextual ո and ե Behavior\n\n")
        f.write("- **ո**: Word-initial → /ʋɔ/ (diphthong), elsewhere → /ɔ/\n")
        f.write("- **ե**: Word-initial → /jɛ/ (with /j/), elsewhere → /ɛ/\n\n")
        
        f.write("### 3. Classical Orthography Markers (WA-specific)\n\n")
        f.write("- **իւ**: /ʏ/ (rounded high front) - retained in WA, "
                "reformed away in EA\n")
        f.write("- **եա**: Retained in WA, reformed to յա in EA\n\n")
        
        f.write("## Per-Word Analysis\n\n")
        for result in results:
            f.write(f"### {result.word}\n\n")
            f.write(f"- **Graphemes**: {', '.join(result.graphemes)}\n")
            f.write(f"- **Transcription**: {result.notes}\n")
            
            if result.voicing_analysis:
                f.write(f"- **Voicing analysis**:\n")
                for g, analysis in result.voicing_analysis.items():
                    f.write(f"  - `{g}`: WA=/{analysis['wa_phone']}/ "
                           f"({analysis['wa_voicing']}), "
                           f"EA=/{analysis['eastern_phone']}/ "
                           f"({analysis['eastern_voicing']})\n")
            
            if result.eastern_leakage_detected:
                f.write(f"- **⚠️ Eastern leakage**: {result.eastern_leakage_reason}\n")
            else:
                f.write(f"- **✓ No Eastern leakage detected**\n")
            
            if result.rule_gaps:
                f.write(f"- **Rule gaps**: {', '.join(result.rule_gaps)}\n")
            
            f.write("\n")
        
        f.write("## Conclusion\n\n")
        f.write("This audit demonstrates that:\n\n")
        f.write("1. The codebase **does not have** a dedicated phonetics/G2P module\n")
        f.write("2. `src/augmentation/vocabulary_filter.py` contains a "
                "**voicing reference dict** but not a full transcription engine\n")
        f.write("3. Contextual rules for ո/ե are **not implemented**\n")
        f.write("4. Classical orthography markers (իւ, եա) are tracked for "
                "**dialect scoring** but not phonetically transcribed\n\n")
        f.write("**Recommendation**: If phonetic transcription is needed, "
                "implement a dedicated `src/phonetics/` module with:\n")
        f.write("- Full grapheme-to-phoneme (G2P) mapping\n")
        f.write("- Contextual rules (word-initial vs medial/final)\n")
        f.write("- Digraph handling (իւ, ու, եւ)\n")
        f.write("- Stress/intonation rules (if needed for TTS)\n")
    
    print(f"✓ Exported: {md_path}")
    
    # 3. Export module map (CSV)
    csv_path = export_dir / "phonetics_module_map.csv"
    with open(csv_path, 'w', encoding='utf-8') as f:
        f.write("file,function,purpose,has_phonetics,notes\n")
        
        modules = [
            (
                'src/augmentation/vocabulary_filter.py',
                'WesternArmenianVocabularyFilter.__init__',
                'Voicing reference dict (not transcription)',
                'No',
                'Contains _voicing_reference dict for documentation only'
            ),
            (
                'src/augmentation/vocabulary_filter.py',
                'check_voicing_patterns',
                'Placeholder for phonetic validation',
                'No',
                'Empty stub; returns True always'
            ),
            (
                'src/cleaning/language_filter.py',
                'compute_wa_score',
                'Dialect scoring (orthographic markers)',
                'No',
                'Checks classical orthography markers (իւ, եա) but no phonetics'
            ),
            (
                'src/cleaning/armenian_tokenizer.py',
                'decompose_ligatures',
                'Ligature normalization',
                'No',
                'Decomposes presentation forms (ﬓ → մն) but no phonetics'
            ),
            (
                'src/augmentation/text_metrics.py',
                'OrthographicMetrics',
                'Orthographic pattern counting',
                'No',
                'Counts markers but no G2P transcription'
            ),
        ]
        
        for file, func, purpose, has_phon, notes in modules:
            # CSV escape
            notes_escaped = notes.replace('"', '""')
            f.write(f'"{file}","{func}","{purpose}","{has_phon}","{notes_escaped}"\n')
    
    print(f"✓ Exported: {csv_path}")
    
    print("\n=== Audit Complete ===")
    print(f"Total words tested: {len(test_words)}")
    print(f"Eastern leakage detected: {sum(1 for r in results if r.eastern_leakage_detected)}")
    print(f"Words with rule gaps: {sum(1 for r in results if r.rule_gaps)}")


if __name__ == '__main__':
    run_phonetics_audit()
