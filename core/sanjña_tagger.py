"""
Sañjñā Tagger — Phase 0 of the Pāṇinian Derivation Engine.

Computes token-level technical labels (sañjñās) from the Sañjñā sūtras (1.1.x)
before any operational (Vidhi) rule fires. This is the only way to implement
rule conditions that require morphological knowledge, e.g.:
  - Pragṛhya immunity (1.1.11–19): certain tokens must NOT undergo vowel sandhi
  - Padānta (1.4.14): every phoneme at a word boundary
  - Āmreḍita (8.1.2): a reduplicated token

Architecture:
  Every sañjñā is a named predicate: SanjnaName -> List[Predicate].
  A predicate is a function (token_slp1: str, morph: dict) -> bool.
  When ANY predicate for a sañjñā fires, the token gets that tag.

The tags are stored in ExecutionContext.sanjña_map and read by
_is_config_condition_match via ConditionSpec.sanjña_required / .prohibit_if_sanjña.
"""

from typing import Dict, Set, List, Callable, Any, Optional
from core.shiva_sutras import PratyaharaResolver

# ---------------------------------------------------------------------------
# Phoneme sets needed for predicate evaluation
# ---------------------------------------------------------------------------
try:
    _VOWELS = set(PratyaharaResolver.resolve_list("aC"))
    _DIPHTHONGS = set(PratyaharaResolver.resolve_list("eN"))   # e, o, ai, au
    _LONG_VOWELS = set(PratyaharaResolver.resolve_list("Ak"))  # long vowels
except Exception:
    _VOWELS = set("aAiIuUfFeEoO")
    _DIPHTHONGS = set("eEoO")
    _LONG_VOWELS = set("AIUFeEoO")

# Dual ending vowels used in 1.1.11 (ī, ū, e in dvivacana)
_DUAL_VOWELS_SLP1 = frozenset({"I", "U", "e"})

# Known nipāta (particle) stems in SLP1 (non-exhaustive; morphological layer should provide flag)
_COMMON_NIPATAS = frozenset({
    "ca", "vA", "ha", "eva", "iva", "tu", "api", "aho", "aho iti",
    "nanu", "nu", "khalu", "cet", "yadi", "AtmA", "asau",
    "U", "A", "O", "he",
})

# Avyaya (indeclinable) stems that end in 'o' and are pragṛhya (1.1.15)
_AVYAYA_O_ENDINGS = frozenset({
    "aho", "ito", "tato", "ato", "yato", "kutas", "mA", "vA"
})

# ---------------------------------------------------------------------------
# Predicate definitions by sañjñā
# ---------------------------------------------------------------------------

SanjnaPredicateFn = Callable[[str, Dict[str, Any]], bool]


def _is_dual_ending(tok: str, morph: Dict[str, Any]) -> bool:
    """1.1.11: dual endings in ī, ū, e are pragṛhya."""
    if morph.get("is_dual") and tok and tok[-1] in _DUAL_VOWELS_SLP1:
        return True
    return False


def _is_adas_mat(tok: str, morph: Dict[str, Any]) -> bool:
    """1.1.12: forms of 'adas' ending in 'mat' are pragṛhya (amī, amū, etc.)."""
    return morph.get("lemma") == "adas" and tok.endswith(("mI", "mU"))


def _is_se_ending(tok: str, morph: Dict[str, Any]) -> bool:
    """1.1.13: the particle 'se' is pragṛhya."""
    return tok in {"se", "sE"}


def _is_nipata_single_vowel(tok: str, morph: Dict[str, Any]) -> bool:
    """1.1.14: a nipāta consisting of a single vowel is pragṛhya."""
    if not morph.get("is_nipata"):
        return False
    vowel_chars = [c for c in tok if c in _VOWELS]
    consonants = [c for c in tok if c not in _VOWELS]
    return len(vowel_chars) == 1 and not consonants


def _is_ot_pragrhya(tok: str, morph: Dict[str, Any]) -> bool:
    """
    1.1.15 ot: any avyaya (indeclinable/particle) ending in 'o' is pragṛhya.
    This covers 'aho', 'ito', etc.
    """
    return tok.endswith("o") and (
        morph.get("is_nipata") or
        morph.get("is_avyaya") or
        tok in _AVYAYA_O_ENDINGS
    )


def _is_padanta(_tok: str, _morph: Dict[str, Any]) -> bool:
    """1.4.14: every phoneme at the end of a pada is padānta. Always True at boundary."""
    return True


def _is_amredita(tok: str, morph: Dict[str, Any]) -> bool:
    """8.1.2: an āmreḍita (reduplicated word) carries this tag."""
    return morph.get("is_amredita", False)


# --- Derivational / affix saṃjñās (needed for 3.x–7.x rule conditions) ---
# These predicates read morphological_features from the ExecutionContext.
# When the morphology layer is unwired, they degrade gracefully (return False).

def _is_dhatu(tok: str, morph: Dict[str, Any]) -> bool:
    """A verbal root (dhātu). Read from morph['category'] == 'dhatu'."""
    return morph.get("category") == "dhatu" or morph.get("is_dhatu", False)


def _is_sup(tok: str, morph: Dict[str, Any]) -> bool:
    """A nominal case affix (sup)."""
    return morph.get("category") == "sup" or morph.get("is_sup", False)


def _is_ting(tok: str, morph: Dict[str, Any]) -> bool:
    """A verbal tense/mood affix (tiṅ)."""
    return morph.get("category") == "ting" or morph.get("is_ting", False)


def _is_krt(tok: str, morph: Dict[str, Any]) -> bool:
    """A kṛt affix (forms nominal derivatives from roots)."""
    return morph.get("category") == "krt" or morph.get("is_krt", False)


def _is_ardhadhatuka(tok: str, morph: Dict[str, Any]) -> bool:
    """An ārdhadhātuka affix (a class of verbal endings)."""
    return morph.get("affix_class") == "ardhadhatuka" or morph.get("is_ardhadhatuka", False)


def _is_sarvadhatuka(tok: str, morph: Dict[str, Any]) -> bool:
    """A sārvadhātuka affix (the other class of verbal endings)."""
    return morph.get("affix_class") == "sarvadhatuka" or morph.get("is_sarvadhatuka", False)


def _is_gati(tok: str, morph: Dict[str, Any]) -> bool:
    """A gati (preverb/preposition) — upasarga."""
    return morph.get("category") == "gati" or morph.get("is_gati", False)


def _is_sarvanamasthana(tok: str, morph: Dict[str, Any]) -> bool:
    """A sarvanāmasthāna (pronoun stem, triggers special endings)."""
    return morph.get("category") == "sarvanamasthana" or morph.get("is_sarvanamasthana", False)


# --- Pratyāhāra saṃjñās (phonological labels referenced by 6.1 rules) ---
# These are assigned based on the token's final phoneme, not morphology.

def _ends_in_pratyahara(token: str, prat: str) -> bool:
    """True if the token's relevant boundary phoneme is in the pratyāhāra."""
    if not token:
        return False
    try:
        phonemes = set(PratyaharaResolver.resolve_list(prat))
        return token[-1] in phonemes
    except Exception:
        return False


def _is_ac(tok: str, morph: Dict[str, Any]) -> bool:
    """The token ends in a vowel (ac pratyāhāra)."""
    return _ends_in_pratyahara(tok, "aC")


def _is_ik(tok: str, morph: Dict[str, Any]) -> bool:
    """The token ends in i/u/ṛ/ḷ (iK pratyāhāra)."""
    return _ends_in_pratyahara(tok, "iK")


def _is_ak(tok: str, morph: Dict[str, Any]) -> bool:
    """The token ends in a simple vowel (aK pratyāhāra)."""
    return _ends_in_pratyahara(tok, "aK")


def _is_hal(tok: str, morph: Dict[str, Any]) -> bool:
    """The token ends in a consonant (hal pratyāhāra)."""
    if not tok:
        return False
    try:
        consonants = set(PratyaharaResolver.resolve_list("hal"))
        return tok[-1] in consonants
    except Exception:
        return False


# Map: sañjñā name (SLP1 normalized) -> list of predicates
SANJÑA_PREDICATES: Dict[str, List[SanjnaPredicateFn]] = {
    # --- Pragṛhya (1.1.11–19): no vowel sandhi —-
    "pragrhya": [
        _is_dual_ending,        # 1.1.11
        _is_adas_mat,           # 1.1.12
        _is_se_ending,          # 1.1.13
        _is_nipata_single_vowel, # 1.1.14
        _is_ot_pragrhya,        # 1.1.15 ot — the critical one for 'aho'
    ],
    # --- Padānta (1.4.14): end of word boundary —-
    "padanta": [
        _is_padanta,            # 1.4.14 — always applies at word boundary
    ],
    # --- Āmreḍita (8.1.2): reduplicated form —-
    "amredita": [
        _is_amredita,           # 8.1.2
    ],
    # --- Nipāta (general particle classification) —-
    "nipata": [
        lambda tok, morph: morph.get("is_nipata", False) or tok in _COMMON_NIPATAS,
    ],
    # --- Avyaya (indeclinable) —-
    "avyaya": [
        lambda tok, morph: morph.get("is_avyaya", False),
    ],
    # --- Derivational / affix saṃjñās (3.x–7.x conditions) —-
    "dhatu": [_is_dhatu],
    "sup": [_is_sup],
    "ting": [_is_ting],
    "krt": [_is_krt],
    "ardhadhatuka": [_is_ardhadhatuka],
    "sarvadhatuka": [_is_sarvadhatuka],
    "gati": [_is_gati],
    "sarvanamasthana": [_is_sarvanamasthana],
    # --- Pratyāhāra saṃjñās (phonological labels) —-
    "ac": [_is_ac],
    "iK": [_is_ik],
    "aK": [_is_ak],
    "hal": [_is_hal],
}


class SanjanaTagger:
    """
    Computes sañjñā (technical label) sets for a pair of input tokens.

    Usage:
        tags = SanjanaTagger.tag(left_token_slp1, right_token_slp1,
                                  left_morph={}, right_morph={})
        # tags == {'left': {'padanta', ...}, 'right': {'padanta', ...}}
    """

    @classmethod
    def tag(
        cls,
        left_token: str,
        right_token: str,
        left_morph: Optional[Dict[str, Any]] = None,
        right_morph: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Set[str]]:
        """
        Run all sañjñā predicates and return a mapping:
        {'left': set_of_sanjnas, 'right': set_of_sanjnas}
        """
        left_morph = left_morph or {}
        right_morph = right_morph or {}

        return {
            "left": cls._tag_single(left_token, left_morph),
            "right": cls._tag_single(right_token, right_morph),
        }

    @classmethod
    def _tag_single(cls, token: str, morph: Dict[str, Any]) -> Set[str]:
        """Return all sañjñā names that apply to a single token."""
        result: Set[str] = set()
        for sanjña, predicates in SANJÑA_PREDICATES.items():
            for pred in predicates:
                try:
                    if pred(token, morph):
                        result.add(sanjña)
                        break  # One predicate firing is enough
                except Exception:
                    pass
        return result

    @classmethod
    def is_pragrhya(cls, token_slp1: str, morph: Optional[Dict[str, Any]] = None) -> bool:
        """
        Convenience: check if a token is Pragṛhya.
        Used by dispatch_forward Phase 2 (Prakṛtibhāva check).
        """
        morph = morph or {}
        return "pragrhya" in cls._tag_single(token_slp1, morph)
