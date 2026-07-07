"""
The 14 Māheśvara Sūtras (Shiva Sutras) and Pratyāhāra Generator.

Pāṇini rearranged the Sanskrit phoneme inventory into 14 aphorisms designed to dynamically
generate character classes (Pratyāhāras) via rule 1.1.71 (ādir antyena sahaitā).

A pratyāhāra is valid IFF:
  - its first part is a phoneme that appears in some Śiva Sūtra, AND
  - its final character (the IT marker) is the IT marker of that same or a later Śiva Sūtra.

No hardcoded allowlist is needed — validity is derived from the Śiva Sūtras themselves.
The only special case is `ra` (r, l) which is conventionally treated as a pratyāhāra even
though it is a single-phoneme edge case, and the duplicate IT marker `R` (sūtras 1 and 6)
which is disambiguated by the `long_an` flag.
"""

from typing import List, Tuple, FrozenSet, Dict, Optional

# Each Sūtra is represented as (tuple_of_phonemes_SLP1, IT_marker_SLP1)
SHIVA_SUTRAS: List[Tuple[Tuple[str, ...], str]] = [
    (('a', 'i', 'u'), 'R'),                        # 1. a i u Ṇ
    (('f', 'x'), 'k'),                             # 2. ṛ ḷ K
    (('e', 'o'), 'N'),                             # 3. e o Ṅ
    (('E', 'O'), 'c'),                             # 4. ai au C
    (('h', 'y', 'v', 'r'), 'w'),                   # 5. ha ya va ra Ṭ
    (('l',), 'R'),                                 # 6. la Ṇ
    (('Y', 'm', 'N', 'R', 'n'), 'm'),              # 7. ña ma ṅa ṇa na M
    (('J', 'B'), 'Y'),                             # 8. jha bha Ñ
    (('G', 'Q', 'D'), 'z'),                        # 9. gha ḍha dha Ṣ
    (('j', 'b', 'g', 'q', 'd'), 'S'),              # 10. ja ba ga ḍa da Ś
    (('K', 'P', 'C', 'W', 'T', 'c', 'w', 't'), 'v'), # 11. kha pha cha ṭha tha ca ṭa ta V
    (('k', 'p'), 'y'),                             # 12. ka pa Y
    (('S', 'z', 's'), 'r'),                        # 13. śa ṣa sa R
    (('h',), 'l')                                  # 14. ha L
]

# Precomputed: set of all phonemes that appear in any Śiva Sūtra.
_ALL_PHONEMES: FrozenSet[str] = frozenset({p for s, _ in SHIVA_SUTRAS for p in s})

# Precomputed: ordered location (sutra_idx, pos_idx) for each phoneme.
_PHONEME_LOCATIONS: Dict[str, Tuple[int, int]] = {}
for _s_idx, (_phonemes, _) in enumerate(SHIVA_SUTRAS):
    for _p_idx, _p in enumerate(_phonemes):
        _PHONEME_LOCATIONS.setdefault(_p, (_s_idx, _p_idx))

# Case-insensitive IT marker lookup: maps lowercase(ch) → actual IT marker.
_IT_MARKERS_BY_LOWER: Dict[str, str] = {}
for _it in [it for _, it in SHIVA_SUTRAS]:
    _IT_MARKERS_BY_LOWER[_it.lower()] = _it

# Common transliteration aliases for SLP1 phonemes.
# Maps non-SLP1 or mixed-case forms → canonical SLP1 phoneme.
_PHONEME_ALIASES: Dict[str, str] = {
    'jh': 'J', 'gh': 'G', 'dh': 'D', 'bh': 'B',
    'kh': 'K', 'ch': 'C', 'th': 'T', 'ph': 'P',
    'jhA': 'J', 'ghA': 'G', 'dhA': 'D', 'bhA': 'B',
    'ṭh': 'W', 'ḍh': 'Q',
}


def _normalize_start_char(start_char: str) -> str:
    """Normalize a start char to a canonical SLP1 phoneme in the Śiva Sūtras."""
    if start_char in _ALL_PHONEMES:
        return start_char
    # Try alias map (jh→J, gh→G, etc.)
    if start_char in _PHONEME_ALIASES:
        return _PHONEME_ALIASES[start_char]
    # Strip trailing 'a' and retry (jha→jh→J via alias, ka→k, etc.)
    if len(start_char) >= 2 and start_char.endswith('a'):
        stripped = start_char[:-1]
        if stripped in _ALL_PHONEMES:
            return stripped
        if stripped in _PHONEME_ALIASES:
            return _PHONEME_ALIASES[stripped]
    # Try case-insensitive match against known phonemes.
    lower = start_char.lower()
    for p in _ALL_PHONEMES:
        if p.lower() == lower:
            return p
    return start_char


def _normalize_it_marker(it_marker: str) -> str:
    """Normalize an IT marker to the actual case used in SHIVA_SUTRAS."""
    if it_marker in _IT_MARKERS_BY_LOWER.values():
        return it_marker
    lower = it_marker.lower()
    if lower in _IT_MARKERS_BY_LOWER:
        return _IT_MARKERS_BY_LOWER[lower]
    return it_marker


def _find_end_sutra(start_char: str, it_marker: str, start_sutra_idx: int, long_an: bool) -> int:
    """Find the index of the Śiva Sūtra whose IT marker terminates the pratyāhāra."""
    for s_idx in range(start_sutra_idx, len(SHIVA_SUTRAS)):
        phonemes, it = SHIVA_SUTRAS[s_idx]
        if it != it_marker:
            continue
        # Handle duplicate IT marker 'R' (sūtra 1 vs sūtra 6).
        if it_marker == 'R' and start_char == 'a':
            if not long_an and s_idx == 0:
                return 0
            if long_an and s_idx == 5:
                return 5
            continue
        return s_idx
    return -1


def _resolve_phonemes(name: str, long_an: bool) -> Tuple[List[str], int, int]:
    """Core resolution shared by resolve() and resolve_list().

    Returns (collected_phonemes, start_sutra_idx, end_sutra_idx).
    Raises ValueError with a descriptive message on invalid input.
    """
    # Special case: `ra` is conventionally (r, l).
    if name == 'ra':
        return (['r', 'l'], -1, -1)

    if len(name) < 2:
        raise ValueError(f"Invalid pratyāhāra name (too short): {name!r}")

    start_char = _normalize_start_char(name[:-1])
    it_marker = _normalize_it_marker(name[-1])

    if start_char not in _ALL_PHONEMES:
        raise ValueError(
            f"Pratyāhāra {name!r}: starting phoneme {start_char!r} not found in Śiva Sūtras"
        )
    if it_marker not in _IT_MARKERS_BY_LOWER.values():
        raise ValueError(
            f"Pratyāhāra {name!r}: IT marker {it_marker!r} not a Śiva Sūtra terminator"
        )

    start_sutra_idx, start_pos_idx = _PHONEME_LOCATIONS[start_char]
    end_sutra_idx = _find_end_sutra(start_char, it_marker, start_sutra_idx, long_an)
    if end_sutra_idx == -1:
        raise ValueError(
            f"Pratyāhāra {name!r}: IT marker {it_marker!r} not found at or after {start_char!r}"
        )

    collected: List[str] = []
    for s_idx in range(start_sutra_idx, end_sutra_idx + 1):
        phonemes, _ = SHIVA_SUTRAS[s_idx]
        if s_idx == start_sutra_idx:
            collected.extend(phonemes[start_pos_idx:])
        else:
            collected.extend(phonemes)

    return (collected, start_sutra_idx, end_sutra_idx)


class PratyaharaResolver:
    """Dynamic generator and cache for Pāṇinian Pratyāhāras.

    Validity is derived from the Śiva Sūtras, not from a hardcoded allowlist.
    Any (start-phoneme, IT-marker) pair that satisfies 1.1.71 is accepted.
    """

    _cache: Dict[Tuple[str, bool], FrozenSet[str]] = {}
    _list_cache: Dict[Tuple[str, bool], Tuple[str, ...]] = {}

    @classmethod
    def resolve(cls, name: str, long_an: bool = False) -> FrozenSet[str]:
        """Resolve a Pratyāhāra string (e.g. 'aC', 'iK', 'jaL', 'hal') to a frozenset of phonemes."""
        cache_key = (name, long_an)
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        collected, _, _ = _resolve_phonemes(name, long_an)
        res_set = frozenset(collected)
        cls._cache[cache_key] = res_set
        return res_set

    @classmethod
    def resolve_list(cls, name: str, long_an: bool = False) -> Tuple[str, ...]:
        """Resolve a Pratyāhāra string to an ordered tuple of phonemes preserving exact
        Pāṇinian index ordering. Crucial for 1.3.10 (yathāsaṅkhyam anudeśaḥ samānām)."""
        cache_key = (name, long_an)
        if cache_key in cls._list_cache:
            return cls._list_cache[cache_key]

        collected, _, _ = _resolve_phonemes(name, long_an)
        res_tuple = tuple(collected)
        cls._list_cache[cache_key] = res_tuple
        return res_tuple

    @classmethod
    def is_valid(cls, name: str) -> bool:
        """Check whether a string is a valid pratyāhāra per the Śiva Sūtras."""
        try:
            cls.resolve(name)
            return True
        except (ValueError, IndexError):
            return False

    @classmethod
    def contains(cls, pratyahara: str, phoneme: str, long_an: bool = False) -> bool:
        """Check if a phoneme (or its savarṇa long form) belongs to a Pratyāhāra."""
        resolved = cls.resolve(pratyahara, long_an=long_an)
        if phoneme in resolved:
            return True
        # Pāṇini 1.1.69: Savarṇa expansion for vowels
        savarna_short = {'A': 'a', 'I': 'i', 'U': 'u', 'F': 'f', 'X': 'x'}
        if phoneme in savarna_short and savarna_short[phoneme] in resolved:
            return True
        return False


# Backward-compatibility: derive all valid pratyāhāras from the Śiva Sūtras.
def _generate_canonical_set() -> FrozenSet[str]:
    """Generate every valid pratyāhāra from the Śiva Sūtras (no hardcoding)."""
    out = set()
    out.add('ra')
    for phoneme in _ALL_PHONEMES:
        s_idx, _ = _PHONEME_LOCATIONS[phoneme]
        for later_idx in range(s_idx, len(SHIVA_SUTRAS)):
            it = SHIVA_SUTRAS[later_idx][1]
            name = phoneme + it
            out.add(name)
            # Also add the variant with uppercase IT (common convention).
            out.add(phoneme + it.upper())
            out.add(phoneme + it.lower())
    return frozenset(out)


CANONICAL_PRATYAHARAS: FrozenSet[str] = _generate_canonical_set()