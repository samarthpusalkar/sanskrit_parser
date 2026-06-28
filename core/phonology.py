"""
Classical and Vedic Phonology module.

Encodes Sanskrit phonemes in SLP1 (1 ASCII character per phoneme) for O(1) string slicing
and deterministic rule matching. Provides converters for IAST and Devanagari.
"""

from enum import Enum, auto
from typing import Dict, Set, List, Tuple


class Sthana(Enum):
    """Point of articulation (Mouth position)."""
    KANTHYA = auto()    # Velar / Throat
    TALAVYA = auto()    # Palatal
    MURDHANYA = auto()  # Retroflex
    DANTYA = auto()     # Dental
    OSTHYA = auto()     # Labial
    NASIKA = auto()     # Nasal
    KANTHA_TALU = auto()
    KANTHA_OSTHA = auto()
    DANTOSTHA = auto()


class Prayatna(Enum):
    """Internal effort of articulation."""
    SPURSTA = auto()          # Stop (Plosive)
    ISAT_SPURSTA = auto()     # Approximant / Semivowel
    ISAT_VIVARTA = auto()     # Fricative / Sibilant
    VIVARTA = auto()          # Open (Vowels)
    SAMVARTA = auto()         # Closed (short 'a' in realization)


class Accent(Enum):
    """Vedic / Classical Tonal Pitch Accent."""
    UDATTA = auto()     # High pitch
    ANUDATTA = auto()   # Low pitch
    SVARITA = auto()    # Falling / Circumflex pitch


# SLP1 Vowel Sets
SHORT_VOWELS = frozenset({'a', 'i', 'u', 'f', 'x'})  # a, i, u, ṛ, ḷ
LONG_VOWELS = frozenset({'A', 'I', 'U', 'F', 'X', 'e', 'E', 'o', 'O'})
PLUTA_MARKER = '3'  # 3-mora prolongation marker per Pāṇini 1.2.27
VOWELS = SHORT_VOWELS | LONG_VOWELS
VISARGA_ALLOPHONES = frozenset({'H', 'ḥ', 's'})


def ends_with_vowel(word: str) -> bool:
    """Check if word ends in a vowel or pluta prolonged vowel."""
    return bool(word) and (word[-1] in VOWELS or word[-1] == PLUTA_MARKER)


def starts_with_vowel(word: str) -> bool:
    """Check if word begins with a vowel."""
    return bool(word) and word[0] in VOWELS

# Guna and Vriddhi tables (SLP1)
GUNA_MAP = {
    'i': 'e', 'I': 'e',
    'u': 'o', 'U': 'o',
    'f': 'ar', 'F': 'ar',
    'x': 'al', 'X': 'al',
    'a': 'a', 'A': 'A'
}

VRIDDHI_MAP = {
    'a': 'A', 'A': 'A',
    'i': 'E', 'I': 'E',
    'u': 'O', 'U': 'O',
    'f': 'Ar', 'F': 'Ar',
    'x': 'Al', 'X': 'Al',
    'e': 'E', 'E': 'E',
    'o': 'O', 'O': 'O'
}

SAVARNA_LONG = {
    'a': 'A', 'A': 'A',
    'i': 'I', 'I': 'I',
    'u': 'U', 'U': 'U',
    'f': 'F', 'F': 'F',
    'x': 'X', 'X': 'X'
}

# SLP1 Consonant Inventory
STOPS = frozenset({
    'k', 'K', 'g', 'G', 'N',
    'c', 'C', 'j', 'J', 'Y',
    'w', 'W', 'q', 'Q', 'R',
    't', 'T', 'd', 'D', 'n',
    'p', 'P', 'b', 'B', 'm'
})

SEMIVOWELS = frozenset({'y', 'r', 'l', 'v'})
SIBILANTS = frozenset({'S', 'z', 's', 'h'})
CONSONANTS = STOPS | SEMIVOWELS | SIBILANTS

# Modifiers
AYOGAVAHA = frozenset({'M', 'H', '~'})  # Anusvara, Visarga, Candrabindu

# Transliteration Maps (SLP1 <-> IAST)
SLP1_TO_IAST = {
    'a': 'a', 'A': 'ā', 'i': 'i', 'I': 'ī', 'u': 'u', 'U': 'ū',
    'f': 'ṛ', 'F': 'ṝ', 'x': 'ḷ', 'X': 'ḹ',
    'e': 'e', 'E': 'ai', 'o': 'o', 'O': 'au',
    'M': 'ṃ', 'H': 'ḥ', '~': 'm̐',
    'k': 'k', 'K': 'kh', 'g': 'g', 'G': 'gh', 'N': 'ṅ',
    'c': 'c', 'C': 'ch', 'j': 'j', 'J': 'jh', 'Y': 'ñ',
    'w': 'ṭ', 'W': 'ṭh', 'q': 'ḍ', 'Q': 'ḍh', 'R': 'ṇ',
    't': 't', 'T': 'th', 'd': 'd', 'D': 'dh', 'n': 'n',
    'p': 'p', 'P': 'ph', 'b': 'b', 'B': 'bh', 'm': 'm',
    'y': 'y', 'r': 'r', 'l': 'l', 'v': 'v',
    'S': 'ś', 'z': 'ṣ', 's': 's', 'h': 'h'
}

IAST_TO_SLP1 = {v: k for k, v in SLP1_TO_IAST.items()}
# Handle multi-char IAST tokens in tokenizer
IAST_MULTI_CHARS = sorted([k for k in IAST_TO_SLP1.keys() if len(k) > 1], key=len, reverse=True)


def slp1_to_iast(text: str) -> str:
    """Convert SLP1 encoded Sanskrit string to IAST."""
    res = []
    for char in text:
        res.append(SLP1_TO_IAST.get(char, char))
    return "".join(res)


def iast_to_slp1(text: str) -> str:
    """Convert IAST Sanskrit string to SLP1."""
    res = ""
    i = 0
    n = len(text)
    while i < n:
        matched = False
        for mc in IAST_MULTI_CHARS:
            if text[i:i+len(mc)] == mc:
                res += IAST_TO_SLP1[mc]
                i += len(mc)
                matched = True
                break
        if not matched:
            char = text[i]
            res += IAST_TO_SLP1.get(char, char)
            i += 1
    return res


def get_sthana(phoneme: str) -> Sthana:
    """Return point of articulation for a phoneme."""
    if phoneme in {'a', 'A', 'k', 'K', 'g', 'G', 'N', 'h', 'H'}:
        return Sthana.KANTHYA
    if phoneme in {'i', 'I', 'c', 'C', 'j', 'J', 'Y', 'y', 'S'}:
        return Sthana.TALAVYA
    if phoneme in {'f', 'F', 'w', 'W', 'q', 'Q', 'R', 'r', 'z'}:
        return Sthana.MURDHANYA
    if phoneme in {'x', 'X', 't', 'T', 'd', 'D', 'n', 'l', 's'}:
        return Sthana.DANTYA
    if phoneme in {'u', 'U', 'p', 'P', 'b', 'B', 'm'}:
        return Sthana.OSTHYA
    if phoneme in {'e', 'E'}:
        return Sthana.KANTHA_TALU
    if phoneme in {'o', 'O'}:
        return Sthana.KANTHA_OSTHA
    if phoneme == 'v':
        return Sthana.DANTOSTHA
    if phoneme in {'M', '~'}:
        return Sthana.NASIKA
    return Sthana.KANTHYA


def compute_antaratama(sthani: str, adesha_candidates: List[str]) -> str:
    """
    Pāṇini 1.1.50 (sthāne 'ntaratamaḥ): When multiple substitutes are available,
    select the one whose point of articulation (sthāna) matches the target most closely.
    """
    target_sthana = get_sthana(sthani)
    
    # Direct match
    for cand in adesha_candidates:
        if get_sthana(cand) == target_sthana:
            return cand
            
    # Compound sthāna affinity (e.g. KANTHA_TALU shares TALAVYA)
    affinity = {
        Sthana.TALAVYA: {Sthana.TALAVYA, Sthana.KANTHA_TALU},
        Sthana.OSTHYA: {Sthana.OSTHYA, Sthana.KANTHA_OSTHA, Sthana.DANTOSTHA},
        Sthana.KANTHYA: {Sthana.KANTHYA, Sthana.KANTHA_TALU, Sthana.KANTHA_OSTHA},
    }
    allowed = affinity.get(target_sthana, {target_sthana})
    for cand in adesha_candidates:
        if get_sthana(cand) in allowed:
            return cand
            
    # If no sthāna match exists (e.g. MURDHANYA 'ṛ' or DANTYA 'ḷ' against Guṇa {e, o, a}),
    # choose the neutral throat vowel 'a' over palatal/labial vowels.
    if 'a' in adesha_candidates and target_sthana not in {Sthana.TALAVYA, Sthana.OSTHYA, Sthana.KANTHA_TALU, Sthana.KANTHA_OSTHA}:
        return 'a'
    if 'A' in adesha_candidates and target_sthana not in {Sthana.TALAVYA, Sthana.OSTHYA, Sthana.KANTHA_TALU, Sthana.KANTHA_OSTHA}:
        return 'A'
            
    return adesha_candidates[0] if adesha_candidates else sthani


def compute_ekadesha(l_char: str, r_char: str, op_type: str) -> str:
    """
    Pragmatic computation of Ekādeśa (single substitute for two phonemes)
    using Pāṇinian meta-rules 1.1.50 (sthāne 'ntaratamaḥ) and 1.1.51 (uraṇ raparaḥ).
    """
    # 1. Savarṇa Dīrgha (6.1.101)
    if op_type in {"ekadesha_savarna_dirgha", "merge_savarna", "dirgha"}:
        return SAVARNA_LONG.get(l_char, l_char)

    # 2. Guṇa (1.1.2 adeṅ guṇaḥ -> a, e, o) + 1.1.51 uraṇ raparaḥ
    if op_type in {"ekadesha_guna", "guna"}:
        guna_candidates = ['e', 'o', 'a']
        sub = compute_antaratama(r_char, guna_candidates)
        if r_char in {'f', 'F'}:
            return sub + 'r'  # uraṇ raparaḥ (1.1.51)
        if r_char in {'x', 'X'}:
            return sub + 'l'  # uraṇ raparaḥ (1.1.51)
        return sub

    # 3. Vṛddhi (1.1.1 vṛddhir ādaic -> A, E, O) + 1.1.51 uraṇ raparaḥ
    if op_type in {"ekadesha_vriddhi", "vriddhi"}:
        vriddhi_candidates = ['E', 'O', 'A']
        sub = compute_antaratama(r_char, vriddhi_candidates)
        if r_char in {'f', 'F'}:
            return sub + 'r'  # uraṇ raparaḥ
        if r_char in {'x', 'X'}:
            return sub + 'l'
        return sub

    return r_char


def apply_natva(text: str) -> str:
    """
    Pragmatic computation of Ṇatva (retroflexion of dental 'n' to 'ṇ')
    per Pāṇini 8.4.1 (raṣābhyāṃ no ṇaḥ samānapade), 8.4.2 (aṭ-kupu-āṅ-num-vyavāye 'pi),
    and 8.4.37 (padāntasya exception).
    """
    allowed_intervening = VOWELS | {'h', 'y', 'v', 'r', 'k', 'K', 'g', 'G', 'N', 'p', 'P', 'b', 'B', 'm', 'M'}
    res = list(text)
    n_len = len(res)
    
    trigger_active = False
    for i in range(n_len):
        char = res[i]
        if char in {'r', 'z'}:
            trigger_active = True
        elif trigger_active:
            if char == 'n':
                # Check 8.4.37 padāntasya (blocked if 'n' is the very last character)
                if i < n_len - 1:
                    res[i] = 'R'
            elif char not in allowed_intervening:
                trigger_active = False
                
    return "".join(res)


def apply_shatva(text: str) -> str:
    """
    Pragmatic computation of Ṣatva (retroflexion of dental 's' to 'ṣ')
    per Pāṇini 8.3.55 (apadāntasya mūrdhanyaḥ), 8.3.57 (iṇ-koḥ), and 8.3.59 (ādeśapratyayayoḥ).
    """
    in_vowels = {'i', 'I', 'u', 'U', 'f', 'F', 'x', 'X', 'e', 'E', 'o', 'O'}
    ku_stops = {'k', 'K', 'g', 'G', 'N'}
    triggers = in_vowels | ku_stops | {'r', 'l'}
    allowed_vyavaya = {'M', 'H', 'S', 'z', 's'}
    
    res = list(text)
    n_len = len(res)
    
    for i in range(1, n_len):
        if res[i] == 's':
            # Must not be padānta (word final) per 8.3.55
            if i == n_len - 1 or (i < n_len - 1 and res[i+1] in {' ', '-', '+'}):
                continue
            # Must not be followed by 'r' per 8.3.57 exception
            if i < n_len - 1 and res[i+1] == 'r':
                continue
                
            # Look backward for iṆ or Ku trigger, allowing num/visarjanīya/śar vyavāya (8.3.58)
            j = i - 1
            while j >= 0 and res[j] in allowed_vyavaya:
                j -= 1
            if j >= 0 and res[j] in triggers:
                res[i] = 'z'
                
    return "".join(res)


# Devanagari mapping tables
DEV_VOWELS = {
    'अ': 'a', 'आ': 'A', 'इ': 'i', 'ई': 'I', 'उ': 'u', 'ऊ': 'U',
    'ऋ': 'f', 'ॠ': 'F', 'ऌ': 'x', 'ॡ': 'X', 'ए': 'e', 'ऐ': 'E',
    'ओ': 'o', 'औ': 'O'
}

DEV_CONSONANTS = {
    'क': 'k', 'ख': 'K', 'ग': 'g', 'घ': 'G', 'ङ': 'N',
    'च': 'c', 'छ': 'C', 'ज': 'j', 'झ': 'J', 'ञ': 'Y',
    'ट': 'w', 'ठ': 'W', 'ड': 'q', 'ढ': 'Q', 'ण': 'R',
    'त': 't', 'थ': 'T', 'द': 'd', 'ध': 'D', 'न': 'n',
    'प': 'p', 'फ': 'P', 'ब': 'b', 'भ': 'B', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v', 'श': 'S',
    'ष': 'z', 'स': 's', 'ह': 'h'
}

DEV_MATRAS = {
    'ा': 'A', 'ि': 'i', 'ी': 'I', 'ु': 'u', 'ू': 'U',
    'ृ': 'f', 'ॄ': 'F', 'ॢ': 'x', 'ॣ': 'X', 'े': 'e', 'ै': 'E',
    'ो': 'o', 'ौ': 'O'
}

DEV_MODS = {
    '्': '', 'ः': 'H', 'ं': 'M', 'ँ': '~', 'ऽ': '.'
}

SLP1_TO_DEV_VOWELS = {v: k for k, v in DEV_VOWELS.items()}
SLP1_TO_DEV_CONS = {v: k for k, v in DEV_CONSONANTS.items()}
SLP1_TO_DEV_MATRAS = {v: k for k, v in DEV_MATRAS.items()}


def slp1_to_devanagari(text: str) -> str:
    """Convert SLP1 encoded string to Devanagari."""
    res = ""
    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        # Check two-char vowel matras/vowels (like ai, au? No, SLP1 is strictly 1 char!)
        if char in SLP1_TO_DEV_VOWELS and (i == 0 or text[i-1] in {' ', '-', '+', '/', '_'} or text[i-1] in {'A', 'I', 'U', 'F', 'X', 'e', 'E', 'o', 'O', 'a', 'i', 'u', 'f', 'x'}):
            res += SLP1_TO_DEV_VOWELS[char]
            i += 1
        elif char in SLP1_TO_DEV_CONS:
            res += SLP1_TO_DEV_CONS[char]
            # Check if next char is vowel matra or virama
            if i + 1 < n and text[i+1] in SLP1_TO_DEV_MATRAS:
                res += SLP1_TO_DEV_MATRAS[text[i+1]]
                i += 2
            elif i + 1 < n and text[i+1] == 'a':
                i += 2  # inherent 'a'
            else:
                res += '्'
                i += 1
        elif char == 'H': res += 'ः'; i += 1
        elif char == 'M': res += 'ं'; i += 1
        elif char == '~': res += 'ँ'; i += 1
        else:
            res += char; i += 1
    return res


def devanagari_to_slp1(text: str) -> str:
    """Convert Devanagari string to SLP1."""
    res = ""
    i = 0
    n = len(text)
    while i < n:
        char = text[i]
        if char in DEV_VOWELS:
            res += DEV_VOWELS[char]
            i += 1
        elif char in DEV_CONSONANTS:
            base = DEV_CONSONANTS[char]
            # Lookahead for matra or virama
            if i + 1 < n and text[i+1] in DEV_MATRAS:
                res += base + DEV_MATRAS[text[i+1]]
                i += 2
            elif i + 1 < n and text[i+1] == '्':
                res += base
                i += 2
            else:
                res += base + 'a'
                i += 1
        elif char in DEV_MODS:
            res += DEV_MODS[char]
            i += 1
        else:
            res += char
            i += 1
    return res

