"""Branch-level rule-based Eastern/Western/Classical Armenian dialect and branch classifier."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import List
import unicodedata


@dataclass(frozen=True)
class DialectRule:
    rule_id: str
    branch: str  # "western", "eastern", or "classical"
    weight: float
    pattern: str
    source: str
    note: str


@dataclass
class EvidenceHit:
    rule_id: str
    branch: str  # "western", "eastern", or "classical"
    weight: float
    matched_text: str
    source: str
    note: str


@dataclass
class DialectClassification:
    text: str
    label: str
    confidence: float
    western_score: float
    eastern_score: float
    classical_score: float
    evidence: List[EvidenceHit]

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "label": self.label,
            "confidence": self.confidence,
            "western_score": self.western_score,
            "eastern_score": self.eastern_score,
            "classical_score": self.classical_score,
            "evidence": [asdict(hit) for hit in self.evidence],
        }




# Source-of-truth rule table now in branch_dialect_classifier.py
# IMPORTANT: Western Armenian uses TRADITIONAL (non-reform) orthography.
# Treat Western Armenian as a distinct language variant and do NOT accept
# Soviet/reform/modernized spellings as canonical WA forms. The Nayiri
# dictionary is the authoritative source for Western Armenian spellings.
_CONSOLIDATED_RULES: list[dict] = [
    # Classical orthography digraph indicating WA: իւ (U+056B U+0582) as in 'իւր' ('yur' or 'yu').
    {"rule_id": "WA_CLASSICAL_YU_DIGRAPH", "branch": "western", "weight": 3.0, "pattern": r"իւ", "source": "CLASSICAL_ORTHOGRAPHY_GUIDE", "note": "Classical իւ digraph (WA)"},

    # WA classical diphthong 'եա' (EA reformed to 'յա').
    {"rule_id": "WA_CLASSICAL_EA_DIPHTHONG", "branch": "western", "weight": 2.0, "pattern": r"եա", "source": "CLASSICAL_ORTHOGRAPHY_GUIDE", "note": "classical 'եա' diphthong (WA)"},
    # WA classical word 'յուրաքանչիւր' (each/every) in old orthography.
    {"rule_id": "WA_CLASSICAL_YURAKANCHOOR", "branch": "western", "weight": 4.0, "pattern": r"(^|\s)յուրաքանչիւր($|\s|[\.,;:!?])", "source": "CLASSICAL_ORTHOGRAPHY_GUIDE", "note": "classical word 'յուրաքանչիւր' (each/every)"},

    # WA metonymic classical words
    {"rule_id": "WA_CLASSICAL_LEZOO", "branch": "western", "weight": 1.5, "pattern": r"լեզու", "source": "CLASSICAL_ORTHOGRAPHY_GUIDE", "note": "classical word 'լեզու' (WA)"},

    # WA postposed indefinite article: մը as in 'բան մը' ('muh').
    {"rule_id": "WA_INDEF_ARTICLE_MUH", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)մը($|\s|[\.,;:!?])", "source": "morphology/articles", "note": "postposed indefinite article 'մը' (muh)"},

    # WA present-particle 'կը' used before verb: 'կը գնում եմ'.
    {"rule_id": "WA_PRESENT_PARTICLE_GUH", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)կը($|\s|[\.,;:!?])", "source": "morphology/verbs", "note": "preverbal particle 'կը'"},

    # WA verb prefix 'կ՚' (elided before vowel) as in 'կ՚գում եմ'.
    {"rule_id": "WA_LEXICAL_GOPH", "branch": "western", "weight": 2.0, "pattern": r"(^|\s)կ՚", "source": "morphology/verbs", "note": "WA prefix 'կ՚' (elided before vowel)"},
    # WA 'հիմա' (hima) for 'now' usage.
    {"rule_id": "WA_LEXICAL_HIMA", "branch": "western", "weight": 2.0, "pattern": r"(^|\s)հիմա($|\s|[\.,;:!?])", "source": "morphology/verbs", "note": "WA word 'հիմա' (now)"},
    # WA 'այնպես' (ayspes) and 'այդպես' (aynpes) style.
    {"rule_id": "WA_LEXICAL_AYSBES", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)այսպէս($|\s|[\.,;:!?])", "source": "morphology/lexical", "note": "WA word 'այսպէս'"},
    {"rule_id": "WA_LEXICAL_AYNBES", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)այնպէս($|\s|[\.,;:!?])", "source": "morphology/lexical", "note": "WA word 'այնպէս'"},
    # WA 'ոչինչ' (vochinch) negative quantifier.
    {"rule_id": "WA_LEXICAL_VOCHINCH", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)ոչինչ($|\s|[\.,;:!?])", "source": "morphology/lexical", "note": "WA word 'ոչինչ'"},
    # WA phrase 'բան մը' (pan muh) indefinite.
    {"rule_id": "WA_LEXICAL_PAN_MU", "branch": "western", "weight": 2.0, "pattern": r"(^|\s)բան\sմը($|\s|[\.,;:!?])", "source": "morphology/articles", "note": "WA phrase 'բան մէ'"},

    # WA core vocabulary from textbook (high confidence).
    {"rule_id": "WA_VOCAB_TSERMAG", "branch": "western", "weight": 3.0, "pattern": r"(^|\s)ճերմակ($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'ճերմակ'"},
    {"rule_id": "WA_VOCAB_KHOHANOTS", "branch": "western", "weight": 3.0, "pattern": r"(^|\s)խոհանոց($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'խոհանոց'"},
    {"rule_id": "WA_VOCAB_CHOOR", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)ջուր($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'ջուր'"},
    {"rule_id": "WA_VOCAB_SHABIG", "branch": "western", "weight": 3.0, "pattern": r"(^|\s)շապիկ($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'շապիկ'"},
    {"rule_id": "WA_VOCAB_MANOOK", "branch": "western", "weight": 3.0, "pattern": r"(^|\s)մանուկ($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'մանուկ'"},
    {"rule_id": "WA_VOCAB_DGHA", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)տղայ($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'տղայ'"},
    # EA_VOCAB_TGHA: EA alternative 'տղա' (should be rejected in WA contexts; WA uses 'տղայ')
    {"rule_id": "EA_VOCAB_TGHA", "branch": "eastern", "weight": 3.0, "pattern": r"(^|\s)տղա($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "EA vocab 'տղա' (Eastern form)"},
    # WA_VOCAB_TGHA removed (EA/reform spelling) -- Eastern is still 'տղա'; only 'տղայ' is WA dgha
    {"rule_id": "WA_VOCAB_CHOOR_ALT", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)ճուր($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'ճուր' (alt)"},
    {"rule_id": "WA_VOCAB_KHOSIL", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)խօսիլ($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'խօսիլ'"},
    {"rule_id": "WA_VOCAB_YERTAL", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)երթալ($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'երթալ'"},
    {"rule_id": "WA_VOCAB_UNEL", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)ընել($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'ընել'"},
    {"rule_id": "WA_VOCAB_HASGNAL", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)հասկնալ($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'հասկնալ'"},
    {"rule_id": "WA_VOCAB_ARTEN", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)արդէն($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'արդէն'"},
    {"rule_id": "WA_VOCAB_HAPA", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)հապա($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'հապա' (translit: haba)"},
    {"rule_id": "WA_VOCAB_GIRAGI", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)կիրակի($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'կիրակի'"},

    # WA future particle 'պիտի' as in 'պիտի գամ'.
    {"rule_id": "WA_FUTURE_PARTICLE_BIDI", "branch": "western", "weight": 2.5, "pattern": r"(^|\s)պիտի($|\s|[\.,;:!?])", "source": "morphology/verbs", "note": "future particle 'պիտի'"},

    # WA lexical specifics: 'մենք' and 'գեղեցիկ'.
    {"rule_id": "WA_LEXICAL_MENK", "branch": "western", "weight": 2.0, "pattern": r"(^|\s)մենք($|\s|[\.,;:!?])", "source": "morphology/pronouns", "note": "WA word 'մենք'"},
    {"rule_id": "WA_LEXICAL_KEGHETSIG", "branch": "western", "weight": 1.5, "pattern": r"(^|\s)գեղեցիկ($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA word 'գեղեցիկ'"},

    # WA negative particle 'չը' separate word as in 'չը գնում' (translit 'chuh').
    {"rule_id": "WA_NEG_PARTICLE_CHUH", "branch": "western", "weight": 2.0, "pattern": r"(^|\s)չ(?:ը|(?:եմ|ես|է|էք|են|էին|ուզեմ|ուզես|ուզէ|ուզենք|ուզեք|ուզեն|ուզել))($|\s|[\.,;:!?])", "source": "morphology/verbs", "note": "negative particle/prefix 'չ' forms"},

    # WA negative prefix forms 'չեմ' (chem), 'չес' (ches), 'չէ' (che), 'չենք' (chenk), 'չեք' (chek), 'չեն' (chen) etc.
    {"rule_id": "WA_NEG_PREFIX_CHE", "branch": "western", "weight": 2.0, "pattern": r"(^|\s)չ(?:եմ|ես|է|էք|են|էին|ուզեմ|ուզես|ուզէ|ուզենք|ուզեք|ուզեն|ուզել)($|\s|[\.,;:!?])", "source": "morphology/verbs", "note": "Western negative prefix 'չ' with verb forms (չեմ, չես, չէ, ...)."},

    # WA negative conjunction with 'այլեւս չ...' as in 'այլեւս չգալ'.
    {"rule_id": "WA_NEG_CONJUNCTION_AYL", "branch": "western", "weight": 3.0, "pattern": r"(^|\s)այլեւս\s+չ(?:[\w\u0531-\u058F]*)($|\s|[\.,;:!?])", "source": "morphology/verbs", "note": "negative construction 'այլեւս չ...'"},

    # WA present-onset particle 'կու' + verb forms: 'կու գալիս է'.
    {"rule_id": "WA_PRESENT_ONSET_GU", "branch": "western", "weight": 3.0, "pattern": r"(^|\s)կու(?:նեմ|դեմ|զ|ն|մ|ք|լ)?($|\s|[\.,;:!?])", "source": "morphology/verbs", "note": "present particle + verb forms 'կու...'"},

    # WA locative/dative forms: 'մէջ' and 'նոյն'.
    {"rule_id": "WA_CASE_DATIVE_WITHIN", "branch": "western", "weight": 1.0, "pattern": r"\b(?:մէջ|նոյն)\b", "source": "morphology/case", "note": "localized dative-including forms (narrowed to avoid common EA words)"},

    # WA verbal gerund/participle suffix '-ալու' as in 'խաղալու'.
    {"rule_id": "WA_VERB_PARTICIPLE_ALU", "branch": "western", "weight": 2.0, "pattern": r"\b[\u0561-\u0586]+ալու\b", "source": "morphology/verbs", "note": "WA participle/gerund -ալու (nominalization)"},

    # EA reformed variant for Classical WA 'իւղ' (yugh), EA uses 'յուղ'.
    {"rule_id": "EA_REFORMED_YUGH", "branch": "eastern", "weight": 3.0, "pattern": r"(^|\s)յուղ($|\s|[\.,;:!?])", "source": "CLASSICAL_ORTHOGRAPHY_GUIDE", "note": "reformed 'յուղ' (EA)"},

    # EA reformed variant: Classical 'գիւղ' becomes 'գյուղ'.
    {"rule_id": "EA_REFORMED_GYUGH", "branch": "eastern", "weight": 3.0, "pattern": r"(^|\s)գյուղ($|\s|[\.,;:!?])", "source": "CLASSICAL_ORTHOGRAPHY_GUIDE", "note": "reformed 'գյուղ' (EA)"},

    # EA reformed variant: Classical 'ճիւղ' becomes 'ճյուղ'.
    {"rule_id": "EA_REFORMED_CHYUGH", "branch": "eastern", "weight": 3.0, "pattern": r"(^|\s)ճյուղ($|\s|[\.,;:!?])", "source": "CLASSICAL_ORTHOGRAPHY_GUIDE", "note": "reformed 'ճյուղ' (EA)"},

    # EA reformed variant: Classical 'զամբիւղ' becomes 'զամբյուղ'.
    {"rule_id": "EA_REFORMED_ZAMBYUGH", "branch": "eastern", "weight": 3.0, "pattern": r"(^|\s)զամբյուղ($|\s|[\.,;:!?])", "source": "CLASSICAL_ORTHOGRAPHY_GUIDE", "note": "reformed 'զամբյուղ' (EA)"},

    # EA reformed variant: 'այստեղ' and 'այնտեղ'.
    # Note: these words can appear in Western usage too; weight reduced to avoid overemphasizing against Western examples.
    {"rule_id": "EA_REFORMED_AYSTEGH", "branch": "eastern", "weight": 1.5, "pattern": r"(^|\s)այստեղ($|\s|[\.,;:!?])", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "EA word 'այստեղ' (here)"},
    {"rule_id": "EA_REFORMED_AYNTEGH", "branch": "eastern", "weight": 2.5, "pattern": r"(^|\s)այնտեղ($|\s|[\.,;:!?])", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "EA word 'այնտեղ' (there)"},
    {"rule_id": "EA_REFORMED_TYOON", "branch": "eastern", "weight": 2.0, "pattern": r"(^|\s)թյուն($|\s|[\.,;:!?])", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "EA reformed word 'թյուն' (tyoon)"},

    # EA reformed variant: Classical 'յուրաքանչյուր' remains 'յուրաքանչյուր'.
    {"rule_id": "EA_REFORMED_URACHYUR", "branch": "eastern", "weight": 3.0, "pattern": r"(^|\s)ուրաքանչյուր($|\s|[\.,;:!?])", "source": "CLASSICAL_ORTHOGRAPHY_GUIDE", "note": "reformed 'յուրաքանչիւր' (EA)"},

    # EA reformed digraph marker: 'միյ' in EA forms such as 'միյասին'.
    {"rule_id": "EA_REFORMED_MIYASIN", "branch": "eastern", "weight": 3.0, "pattern": r"(^|\s)միյ", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "EA reformed digraph 'միյ'"},

    # EA transliteration flag words used as known wrong output from WA-focused models.
    {"rule_id": "EA_TRANSLIT_PETIK", "branch": "eastern", "weight": 2.0, "pattern": r"\bpetik\b", "source": "ARMENIAN_QUICK_REFERENCE", "note": "translit cue 'petik' (EA)"},
    {"rule_id": "EA_TRANSLIT_JAYUR", "branch": "eastern", "weight": 2.0, "pattern": r"\bjayur\b", "source": "ARMENIAN_QUICK_REFERENCE", "note": "translit cue 'jayur' (EA)"},

    # EA indefinite article 'մի' appears before noun, compared to WA 'մը'.
    {"rule_id": "EA_INDEF_ARTICLE_MI", "branch": "eastern", "weight": 2.5, "pattern": r"\u0574\u056b\s", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "Eastern indefinite article 'մի' before noun"},

    # EA vocabulary marker 'ձու' (egg) versus WA 'հավկիթ'.
    {"rule_id": "EA_VOCAB_DZU", "branch": "eastern", "weight": 2.5, "pattern": r"\u0571\u0578\u0582", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "EA vocab 'ձու'"},
    {"rule_id": "EA_VOCAB_GNAL", "branch": "eastern", "weight": 2.0, "pattern": r"(^|\s)գնալ($|\s|[\.,;:!?])", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "EA vocab 'գնալ'"},
    {"rule_id": "EA_VOCAB_KHOSEL", "branch": "eastern", "weight": 2.0, "pattern": r"(^|\s)խոսել($|\s|[\.,;:!?])", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "EA vocab 'խոսել'"},

    # WA vocab 'հավկիթ' (havgit) - strongly Western vocabulary.
    {"rule_id": "WA_VOCAB_HAVGIT", "branch": "western", "weight": 2.5, "pattern": r"\u0570\u0561\u057e\u056f\u056b\u0569", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "WA vocab 'հավկիթ'"},
    # WA vocab 'մանչօւգ' (manchoug) - dialect-specific term.
    {"rule_id": "WA_VOCAB_MANCHOUG", "branch": "western", "weight": 3.0, "pattern": r"\u0574\u0561\u0576\u0579\u0578\u0582\u056f", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "WA vocab 'մանչօւգ' (manchoug)"},
    {"rule_id": "WA_VOCAB_ANDZEROTSIK", "branch": "western", "weight": 2.0, "pattern": r"(^|\s)անձեռոցիկ($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'անձեռոցիկ' (napkin)"},
    {"rule_id": "WA_VOCAB_ERKUSHABTI", "branch": "western", "weight": 2.0, "pattern": r"(^|\s)\u0565\u0580\u056f\u0578\u0582\u0577\u0561\u0562\u0569\u056b($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA vocab 'երկুশաբթի' (Monday)"},
    # WA vocab 'երթալ' (yerthal) - common Western verb.
    {"rule_id": "WA_VOCAB_YERTHAL", "branch": "western", "weight": 2.5, "pattern": r"\u0565\u0580\u0569\u0561\u056c", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "WA vocab 'երթալ' (yerthal)"},
    # WA vocab 'ուզել' (ouzel) - core Western verb 'to want'.
    {"rule_id": "WA_VOCAB_OUZEL", "branch": "western", "weight": 2.5, "pattern": r"\u0578\u0582\u0566\u0565\u056c", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "WA vocab 'ուզել' (ouzel)"},
    # WA vocab 'շատ' (shad) - frequent adjective 'very/much'.
    {"rule_id": "WA_VOCAB_SHAD", "branch": "western", "weight": 2.0, "pattern": r"\bշատ\b", "source": "WA_TEXTBOOK_FREQ", "note": "frequent WA adjective 'շատ'"},
    # WA vocab 'լաւ' (lav) - frequent adjective 'good/well'.
    {"rule_id": "WA_VOCAB_LAV", "branch": "western", "weight": 2.0, "pattern": r"\bլաւ\b", "source": "WA_TEXTBOOK_FREQ", "note": "frequent WA adjective 'լաւ'"},
    # WA vocab 'մեծ' (medz) - frequent adjective 'big'.
    {"rule_id": "WA_VOCAB_MEDZ", "branch": "western", "weight": 2.0, "pattern": r"\bմեծ\b", "source": "WA_TEXTBOOK_FREQ", "note": "frequent WA adjective 'մեծ'"},
    # WA vocab 'մէջ' (mech) - locative word meaning 'in/inside'.
    {"rule_id": "WA_VOCAB_MECH", "branch": "western", "weight": 2.0, "pattern": r"\bմէջ\b", "source": "WA_TEXTBOOK_FREQ", "note": "frequent WA locative word 'մէջ'"},

    # Classical WA diphthong endings, very strong evidence.
    {"rule_id": "WA_WORD_ENDING_AY", "branch": "western", "weight": 1.5, "pattern": r"\u0561\u0575(?=[\s\u0589\u055D\u055E,.;:!?]|\Z)", "source": "CLASSICAL_ORTHOGRAPHY_GUIDE", "note": "Word ending -ay (classical WA)"},
    {"rule_id": "WA_WORD_ENDING_OY", "branch": "western", "weight": 2.0, "pattern": r"\u0578\u0575(?=[\s\u0589\u055D\u055E,.;:!?]|\Z)", "source": "CLASSICAL_ORTHOGRAPHY_GUIDE", "note": "Word ending -oy (classical WA)"},
    {"rule_id": "WA_WORD_INTERNAL_E_LONG", "branch": "western", "weight": 1.0, "pattern": r"[\u0531-\u0587]\u0567[\u0531-\u0587]", "source": "CLASSICAL_ORTHOGRAPHY_GUIDE", "note": "Word-internal long-e (classical WA)"},
    {"rule_id": "WA_STANDALONE_AL", "branch": "western", "weight": 1.0, "pattern": r"(^|\s)ալ($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA standalone 'ալ'"},
    {"rule_id": "WA_STANDALONE_GU", "branch": "western", "weight": 2.0, "pattern": r"(^|\s)կը($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA standalone 'կը'"},
    {"rule_id": "WA_STANDALONE_HON", "branch": "western", "weight": 3.0, "pattern": r"(^|\s)հոն($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA standalone 'հոն'"},
    {"rule_id": "WA_STANDALONE_HOS", "branch": "western", "weight": 3.0, "pattern": r"(^|\s)հոս($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA standalone 'հոս'"},
    {"rule_id": "WA_SUFFIX_IL", "branch": "western", "weight": 1.5, "pattern": r"(?<=[\u0531-\u0586])իլ($|\s|[\.,;:!?])", "source": "WA_TEXTBOOK_FREQ", "note": "WA suffix '-իլ'"},
    {"rule_id": "EA_REGEX_UM", "branch": "eastern", "weight": 1.0, "pattern": r"(?<=[\u0531-\u0586])ում($|\s|[\.,;:!?])", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "EA  -ում suffix"},
    {"rule_id": "EA_REGEX_YEV_INTERNAL", "branch": "eastern", "weight": 3.0, "pattern": r"[\u0531-\u0586]\u0587[\u0531-\u0586]", "source": "WA_EA_LINGUISTIC_DISTINCTIONS", "note": "EA internal 'և'"},

    # Classical Grabar accusative prefix 'զ-' in constructions like 'զգալ'.
    {"rule_id": "CL_ACCUSATIVE_Z", "branch": "classical", "weight": 2.0, "pattern": r"\u0566[\u0531-\u058F]", "source": "CLASSICAL_ARMENIAN_IDENTIFICATION", "note": "Grabar accusative prefix 'զ-'"},

    # Liturgical phrase 'Տէր ողորմյա'.
    {"rule_id": "CL_LITURGICAL_DER", "branch": "classical", "weight": 3.0, "pattern": r"\u054f\u0567\u0580\s\u0578\u0572\u0580\u0574\u0575\u0561", "source": "CLASSICAL_ARMENIAN_IDENTIFICATION", "note": "liturgical phrase"},

    # Grabar archaic verb participle ending '-եալ'.
    {"rule_id": "CL_ARCHAIC_VERB_EAL", "branch": "classical", "weight": 1.5, "pattern": r"\u0565\u0561\u056C\b", "source": "CLASSICAL_ARMENIAN_IDENTIFICATION", "note": "archaic participle ending -եալ"},
]

def get_consolidated_rules() -> list[dict]:
    """Return a copy of the consolidated rule list."""
    return list(_CONSOLIDATED_RULES)


def get_eastern_markers() -> list[tuple[str, float]]:
    """Return EA markers from consolidated rules (reform + vocab)."""
    return [
        (rule["pattern"], rule["weight"]) for rule in _CONSOLIDATED_RULES
        if rule.get("branch") == "eastern" and rule.get("rule_id", "").startswith("EA_")
    ]


def get_lexical_markers() -> list[tuple[str, float]]:
    """Return WA lexical markers from consolidated rules."""
    associated_ids = {
        "WA_LEXICAL_GOPH", "WA_LEXICAL_HIMA", "WA_LEXICAL_AYSBES", "WA_LEXICAL_AYNBES",
        "WA_LEXICAL_VOCHINCH", "WA_LEXICAL_PAN_MU", "WA_NEG_PARTICLE_CHUH", "WA_NEG_PREFIX_CHE",
        "WA_NEG_CONJUNCTION_AYL", "WA_PRESENT_ONSET_GU", "WA_CASE_DATIVE_WITHIN", "WA_VERB_PARTICIPLE_ALU",
        "WA_LEXICAL_MENK", "WA_LEXICAL_KEGHETSIG"
    }
    return [
        (rule["pattern"], rule["weight"]) for rule in _CONSOLIDATED_RULES
        if rule.get("branch") == "western" and rule.get("rule_id", "") in associated_ids
    ]


def get_classical_markers() -> list[tuple[str, float]]:
    """Return classical WA markers from consolidated rules."""
    return [
        (rule["pattern"], rule["weight"]) for rule in _CONSOLIDATED_RULES
        if rule.get("branch") == "western" and rule.get("rule_id", "").startswith("WA_CLASSICAL")
    ]


def get_wa_vocabulary_markers() -> list[tuple[str, float]]:
    """Return WA vocabulary markers from consolidated rules."""
    return [
        (rule["pattern"], rule["weight"]) for rule in _CONSOLIDATED_RULES
        if rule.get("branch") == "western" and "VOCAB" in rule.get("rule_id", "")
    ]


def get_wa_standalone_patterns() -> list[tuple[re.Pattern, float]]:
    """Return compiled standalone WA markers."""
    return [
        (re.compile(rule["pattern"], flags=re.IGNORECASE), rule["weight"])
        for rule in _CONSOLIDATED_RULES
        if rule.get("rule_id", "").startswith("WA_STANDALONE_")
    ]


def get_wa_suffix_patterns() -> list[tuple[re.Pattern, float]]:
    """Return compiled WA suffix marker."""
    return [
        (re.compile(rule["pattern"], flags=re.IGNORECASE), rule["weight"])
        for rule in _CONSOLIDATED_RULES
        if rule.get("rule_id", "") == "WA_SUFFIX_IL"
    ]


def get_ea_regex_patterns() -> list[tuple[re.Pattern, float]]:
    """Return compiled EA regex markers."""
    return [
        (re.compile(rule["pattern"], flags=re.IGNORECASE), rule["weight"])
        for rule in _CONSOLIDATED_RULES
        if rule.get("rule_id", "").startswith("EA_REGEX_")
    ]


def get_word_internal_e_long_re() -> re.Pattern:
    """Return compiled WA internal long-e regex."""
    return re.compile(r"[\u0531-\u0587]\u0567[\u0531-\u0587]", flags=re.IGNORECASE)


def get_word_ending_ay_re() -> re.Pattern:
    """Return compiled WA ending ay regex."""
    return re.compile(r"\u0561\u0575(?=[\s\u0589\u055D\u055E,.;:!?]|\Z)", flags=re.IGNORECASE)


def get_word_ending_oy_re() -> re.Pattern:
    """Return compiled WA ending oy regex."""
    return re.compile(r"\u0578\u0575(?=[\s\u0589\u055D\u055E,.;:!?]|\Z)", flags=re.IGNORECASE)


def get_wa_authors() -> list[tuple[str, float]]:
    """Return WA author markers."""
    return [
        (rule["pattern"], rule["weight"]) for rule in _CONSOLIDATED_RULES
        if rule.get("branch") == "western" and rule.get("rule_id", "").startswith("WA_AUTHOR_")
    ]


def get_wa_publication_cities() -> list[tuple[str, float]]:
    """Return WA publication city markers."""
    return [
        (rule["pattern"], rule["weight"]) for rule in _CONSOLIDATED_RULES
        if rule.get("branch") == "western" and rule.get("rule_id", "").startswith("WA_PUBLICATION_CITY_")
    ]


def get_armenian_punctuation() -> frozenset[str]:
    """Return Armenian punctuation set."""
    return frozenset("\u0589\u055D\u055E\u055C\u055A\u058A\u00AB\u00BB")

#TODO need to update this to be more dynamic based on the distribution of scores and thresholds for classification, rather than a fixed value.
def get_wa_score_threshold() -> float:
    """Return current threshold for WA classification."""
    return 5.0


def _rule_includes_marker(marker: str, branch: str) -> bool:
    """Return True if the given marker exists in the given branch of consolidated rules."""

    if branch == "classical":
        candidates = [r for r in _CONSOLIDATED_RULES if r.get("branch") == "western" and (r.get("rule_id", "").startswith("WA_CLASSICAL") or r.get("rule_id") in {"WA_WORD_ENDING_AY", "WA_WORD_ENDING_OY"})]
    elif branch == "lexical":
        candidates = [r for r in _CONSOLIDATED_RULES if r.get("branch") == "western" and (r.get("rule_id", "").startswith("WA_LEXICAL") or r.get("rule_id", "").startswith("WA_PRESENT") or r.get("rule_id", "").startswith("WA_NEG") or r.get("rule_id", "").startswith("WA_"))]
    elif branch == "vocab":
        candidates = [r for r in _CONSOLIDATED_RULES if r.get("branch") == "western" and "VOCAB" in r.get("rule_id", "")]
    elif branch == "eastern":
        candidates = [r for r in _CONSOLIDATED_RULES if r.get("branch") == "eastern"]
    else:
        candidates = [r for r in _CONSOLIDATED_RULES if r.get("branch") == branch]

    return any(rule.get("pattern", "") == marker for rule in candidates)


def _verify_consolidated_rules_consistency() -> None:
    """Ensure markers aggregated from consolidated rules are all present."""
    missing = []

    # Validate classical markers
    for marker, weight in get_classical_markers():
        if not _rule_includes_marker(marker, "western"):
            missing.append(("classical", marker))

    # Validate lexical markers
    for marker, weight in get_lexical_markers():
        if not _rule_includes_marker(marker, "western"):
            missing.append(("lexical", marker))

    # Validate vocabulary markers
    for marker, weight in get_wa_vocabulary_markers():
        if not _rule_includes_marker(marker, "western"):
            missing.append(("vocab", marker))

    # Validate Eastern markers
    for marker, weight in get_eastern_markers():
        if not _rule_includes_marker(marker, "eastern"):
            missing.append(("eastern", marker))

    # WA source tokens are same as classical+lexical+vocab.
    wa_tokens = [m for m, _ in (get_classical_markers() + get_lexical_markers() + get_wa_vocabulary_markers())]
    for token in wa_tokens:
        if not _rule_includes_marker(token, "western"):
            missing.append(("wa_source_token_missing", token))

    if missing:
        raise AssertionError(
            f"Consolidated rules are missing marker coverage for: {missing}"
        )


_CONSOLIDATED_COMPILED: list[tuple[dict, re.Pattern]] = [
    (r, re.compile(r["pattern"], flags=re.IGNORECASE)) for r in _CONSOLIDATED_RULES
]

_CONSOLIDATED_COMPILED = [
    (r, re.compile(r["pattern"], flags=re.IGNORECASE)) for r in _CONSOLIDATED_RULES
]

# Run consistency check at module import
_verify_consolidated_rules_consistency()

def _build_dialect_rules() -> List[DialectRule]:
    rules = []
    for r in _CONSOLIDATED_RULES:
        rules.append(
            DialectRule(
                rule_id=r.get("rule_id", ""),
                branch=r.get("branch", "unknown"),
                weight=float(r.get("weight", 0.0)),
                pattern=r.get("pattern", ""),
                source=r.get("source", ""),
                note=r.get("note", ""),
            )
        )
    return rules


_RULES = _build_dialect_rules()

_COMPILED_RULES = [(rule, re.compile(rule.pattern, flags=re.IGNORECASE)) for rule in _RULES]


def _classify_scores(western_score: float, eastern_score: float, classical_score: float) -> tuple[str, float]:
    total = western_score + eastern_score + classical_score
    if total == 0:
        return "inconclusive", 0.0

    if classical_score >= 3.0 and classical_score >= western_score and classical_score >= eastern_score:
        confidence = round(classical_score / total, 3)
        return "likely_classical", min(confidence, 0.99)

    total_modern = western_score + eastern_score
    if total_modern == 0:
        return "inconclusive", 0.5

    if western_score == eastern_score:
        return "inconclusive", 0.5

    if western_score > eastern_score:
        confidence = round((western_score - eastern_score) / total_modern, 3)
        return "likely_western", confidence

    confidence = round((eastern_score - western_score) / total_modern, 3)
    return "likely_eastern", confidence


def classify_text_classification(text: str) -> dict:
    # Normalize and casefold so pattern matching is robust to Unicode case differences
    normalized = (text or "").strip().casefold()
    western_score = 0.0
    eastern_score = 0.0
    classical_score = 0.0
    evidence: List[EvidenceHit] = []

    # Try matching against a few Unicode normalization forms to account for
    # composed/decomposed or variant spellings in the wild. For each rule,
    # attempt to find a match in these normalized variants and count the rule
    # weight at first match to avoid double-counting the same rule.
    norm_variants = [normalized, unicodedata.normalize("NFC", normalized), unicodedata.normalize("NFD", normalized)]
    for rule, pattern in _COMPILED_RULES:
        matched = False
        for text_variant in norm_variants:
            for match in pattern.finditer(text_variant):
                mt = match.group(0)
                evidence.append(
                    EvidenceHit(
                        rule_id=rule.rule_id,
                        branch=rule.branch,
                        weight=rule.weight,
                        matched_text=mt,
                        source=rule.source,
                        note=rule.note,
                    )
                )
                matched = True
                break
            if matched:
                break
        if matched:
            if rule.branch == "western":
                western_score += rule.weight
            elif rule.branch == "eastern":
                eastern_score += rule.weight
            else:
                classical_score += rule.weight

    label, confidence = _classify_scores(western_score, eastern_score, classical_score)

    return {
        "text": normalized,
        "label": label,
        "confidence": confidence,
        "western_score": round(western_score, 3),
        "eastern_score": round(eastern_score, 3),
        "classical_score": round(classical_score, 3),
        "evidence": [e.__dict__ for e in evidence],
    }


def classify_batch_texts(texts: List[str]) -> List[dict]:
    return [classify_text_classification(t) for t in texts]


def classify_vocab_and_sentences(vocab: List[str], sentences: List[str]) -> dict:
    vocab_results = classify_batch_texts(vocab)
    sentence_results = classify_batch_texts(sentences)
    all_results = vocab_results + sentence_results
    counts = {
        "likely_western": sum(1 for r in all_results if r["label"] == "likely_western"),
        "likely_eastern": sum(1 for r in all_results if r["label"] == "likely_eastern"),
        "likely_classical": sum(1 for r in all_results if r["label"] == "likely_classical"),
        "inconclusive": sum(1 for r in all_results if r["label"] == "inconclusive"),
    }
    return {"vocab": vocab_results, "sentences": sentence_results, "summary": {"total_items": len(all_results), "counts": counts}}


# Convenience helpers for compatibility with existing code that imported
# `compute_wa_score`, `_has_armenian_script`, and `WA_SCORE_THRESHOLD` from
# other helper modules. These are provided here as the direct source-of-truth
# (no shims) as requested.
ARMENIAN_RE = re.compile(r"[\u0531-\u0587]")


def _has_armenian_script(text: str) -> bool:
    """Return True if *text* contains any Armenian script characters."""
    return bool(ARMENIAN_RE.search(text or ""))


def compute_wa_score(text: str) -> float:
    """Return the computed Western Armenian (WA) score for *text*.

    This uses the rule-based classifier's western_score as the WA score.
    """
    res = classify_text_classification(text)
    return float(res.get("western_score", 0.0))


# Export a constant threshold value for callers that expect `WA_SCORE_THRESHOLD`.
WA_SCORE_THRESHOLD: float = get_wa_score_threshold()
