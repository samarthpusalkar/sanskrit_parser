"""
The 14 Māheśvara Sūtras (Shiva Sutras) and Pratyāhāra Generator.

Pāṇini rearranged the Sanskrit phoneme inventory into 14 aphorisms designed to dynamically
generate character classes (Pratyāhāras) via rule 1.1.71 (ādir antyena sahaitā).
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


CANONICAL_PRATYAHARAS: FrozenSet[str] = frozenset({
    'aR', 'iR', 'uR', 'yaR', 'ak', 'ik', 'uk', 'fk', 'eN', 'oN', 'ac', 'ic', 'ec', 'Ec', 'aC', 'iC', 'eC',
    'aw', 'iw', 'am', 'yam', 'Jam', 'Jm', 'ym', 'JaY', 'BaY', 'Baz', 'Jaz', 'jaS', 'baS', 'aS', 'haS',
    'vaS', 'JaS', 'Cav', 'yay', 'may', 'Jay', 'Kay', 'cay', 'yar', 'Jar', 'Kar', 'car', 'Sar',
    'al', 'hal', 'val', 'ral', 'Jal', 'Sal', 'ra', 'yam'
})


class PratyaharaResolver:
    """Dynamic generator and cache for Pāṇinian Pratyāhāras."""

    _cache: Dict[Tuple[str, bool], FrozenSet[str]] = {}

    @classmethod
    def resolve(cls, name: str, long_an: bool = False) -> FrozenSet[str]:
        """
        Resolve a Pratyāhāra string (e.g. 'aC', 'iK', 'haL') to a frozenset of phonemes.
        """
        cache_key = (name, long_an)
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        if name == 'ra':
            res = frozenset({'r', 'l'})
            cls._cache[cache_key] = res
            return res

        if len(name) < 2:
            raise ValueError(f"Invalid pratyāhāra name: {name}")

        # Case-insensitive check against canonical pratyāhāras
        norm = name[:-1] + name[-1].lower()
        norm_up = name[:-1] + name[-1].upper()
        if norm not in CANONICAL_PRATYAHARAS and norm_up not in CANONICAL_PRATYAHARAS and name not in CANONICAL_PRATYAHARAS:
            raise ValueError(f"Non-canonical pratyāhāra rejected: {name}")

        start_char = name[:-1]
        it_marker = name[-1]

        valid_its = [it for _, it in SHIVA_SUTRAS]
        if it_marker not in valid_its and it_marker.lower() in valid_its:
            it_marker = it_marker.lower()

        # Find starting sūtra and position
        all_phonemes_set = {p for s, _ in SHIVA_SUTRAS for p in s}
        if start_char not in all_phonemes_set:
            if start_char.endswith('a') and start_char[:-1] in all_phonemes_set:
                start_char = start_char[:-1]

        start_sutra_idx = -1
        start_pos_idx = -1
        for s_idx, (phonemes, _) in enumerate(SHIVA_SUTRAS):
            if start_char in phonemes:
                start_sutra_idx = s_idx
                start_pos_idx = phonemes.index(start_char)
                break

        if start_sutra_idx == -1:
            raise ValueError(f"Starting phoneme '{start_char}' not found in Shiva Sūtras.")

        # Find ending sūtra by IT marker
        end_sutra_idx = -1
        for s_idx in range(start_sutra_idx, len(SHIVA_SUTRAS)):
            phonemes, it = SHIVA_SUTRAS[s_idx]
            if it == it_marker:
                # Handle duplicate IT marker 'R' (Sūtra 1 vs Sūtra 6)
                if it_marker == 'R' and start_char == 'a':
                    if not long_an and s_idx == 0:
                        end_sutra_idx = 0
                        break
                    elif long_an and s_idx == 5:
                        end_sutra_idx = 5
                        break
                    continue
                end_sutra_idx = s_idx
                break

        if end_sutra_idx == -1:
            raise ValueError(f"IT marker '{it_marker}' not found after '{start_char}'.")

        # Collect all phonemes between start_char and it_marker
        collected: List[str] = []
        for s_idx in range(start_sutra_idx, end_sutra_idx + 1):
            phonemes, _ = SHIVA_SUTRAS[s_idx]
            if s_idx == start_sutra_idx:
                collected.extend(phonemes[start_pos_idx:])
            else:
                collected.extend(phonemes)

        res_set = frozenset(collected)
        cls._cache[cache_key] = res_set
        return res_set

    _list_cache: Dict[Tuple[str, bool], Tuple[str, ...]] = {}

    @classmethod
    def resolve_list(cls, name: str, long_an: bool = False) -> Tuple[str, ...]:
        """
        Resolve a Pratyāhāra string to an ordered tuple of phonemes preserving exact Pāṇinian index ordering.
        Crucial for Sūtra 1.3.10 (yathāsaṅkhyam anudeśaḥ samānām) equal-number 1-to-1 bijection.
        """
        cache_key = (name, long_an)
        if cache_key in cls._list_cache:
            return cls._list_cache[cache_key]

        if name == 'ra':
            res = ('r', 'l')
            cls._list_cache[cache_key] = res
            return res

        if len(name) < 2:
            raise ValueError(f"Invalid pratyāhāra name: {name}")

        start_char = name[:-1]
        it_marker = name[-1]
        valid_its = [it for _, it in SHIVA_SUTRAS]
        if it_marker not in valid_its and it_marker.lower() in valid_its:
            it_marker = it_marker.lower()

        all_phonemes_set = {p for s, _ in SHIVA_SUTRAS for p in s}
        if start_char not in all_phonemes_set:
            if start_char.endswith('a') and start_char[:-1] in all_phonemes_set:
                start_char = start_char[:-1]

        start_sutra_idx = -1
        start_pos_idx = -1
        for s_idx, (phonemes, _) in enumerate(SHIVA_SUTRAS):
            if start_char in phonemes:
                start_sutra_idx = s_idx
                start_pos_idx = phonemes.index(start_char)
                break

        if start_sutra_idx == -1:
            raise ValueError(f"Starting phoneme '{start_char}' not found in Shiva Sūtras.")

        end_sutra_idx = -1
        for s_idx in range(start_sutra_idx, len(SHIVA_SUTRAS)):
            phonemes, it = SHIVA_SUTRAS[s_idx]
            if it == it_marker:
                if it_marker == 'R' and start_char == 'a':
                    if not long_an and s_idx == 0:
                        end_sutra_idx = 0
                        break
                    elif long_an and s_idx == 5:
                        end_sutra_idx = 5
                        break
                    continue
                end_sutra_idx = s_idx
                break

        if end_sutra_idx == -1:
            raise ValueError(f"IT marker '{it_marker}' not found after '{start_char}'.")

        collected: List[str] = []
        for s_idx in range(start_sutra_idx, end_sutra_idx + 1):
            phonemes, _ = SHIVA_SUTRAS[s_idx]
            if s_idx == start_sutra_idx:
                collected.extend(phonemes[start_pos_idx:])
            else:
                collected.extend(phonemes)

        res_tuple = tuple(collected)
        cls._list_cache[cache_key] = res_tuple
        return res_tuple

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
