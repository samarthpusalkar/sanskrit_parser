"""
IT-Marker (Anubandha) Parser and Metadata Flag System.

Pāṇini attached silent letters (Anubandhas / IT-markers) to roots, suffixes, and augments.
These silent markers act as boolean flags governing morphophonemic transformations
(Guṇa/Vṛddhi gradation, accentuation, infix insertion, prohibition).
"""

from dataclasses import dataclass, field
from typing import Set, Dict, List


@dataclass
class MorphemeFlags:
    """Boolean execution flags derived from Anubandhas."""
    vriddhi_trigger: bool = False      # Ṇit or Ñit (7.2.115 aco 'ñṇiti)
    guna_prohibited: bool = False      # Kit or Ṅit (1.1.5 kṅiti ca)
    num_augment: bool = False          # Idit root (7.1.58 idito num dhātoḥ)
    sarvadhatuka_prohibited: bool = False # Śit suffix behaves as Sārvadhātuka (3.4.113)
    final_accent: bool = False         # Cit suffix takes final accent (6.1.163)
    initial_accent: bool = False       # Nit suffix takes initial accent (6.1.197)
    atmanepada_only: bool = False      # Ṅit root (1.3.12 anudāttaṅita ātmanepadam)
    ubhayapada: bool = False           # Ñit root (1.3.72 svaritañita kartṛabhiprāye...)


@dataclass
class ParsedMorpheme:
    """A morpheme separated into its pronounced base and metadata flags."""
    raw: str
    base: str
    it_markers: Set[str] = field(default_factory=set)
    flags: MorphemeFlags = field(default_factory=MorphemeFlags)
    morpheme_type: str = "pratyaya"    # 'root', 'pratyaya', 'agama'


class AnubandhaParser:
    """Parses raw Pāṇinian morphemes and extracts their IT-markers."""

    @classmethod
    def parse(cls, raw: str, morpheme_type: str = "pratyaya") -> ParsedMorpheme:
        """
        Parse raw morpheme (SLP1) into clean base and flags.

        Examples:
            parse("Ric", "pratyaya") -> base="i", it_markers={'R', 'c'}, vriddhi_trigger=True
            parse("Sap", "pratyaya") -> base="a", it_markers={'S', 'p'}
        """
        base = raw
        it_markers: Set[str] = set()

        # Simplified rule-based extraction for classical core inventory
        # 1. Final Hal (1.3.3 hal antyam)
        if len(base) > 1 and cls._is_consonant(base[-1]):
            # Exception 1.3.4: Vibhakti endings ending in t, s, m do not lose them
            if not (morpheme_type == "vibhakti" and base[-1] in {'t', 's', 'm'}):
                it_markers.add(base[-1])
                base = base[:-1]

        # 2. Initial consonants in pratyayas (1.3.6 ṣaḥ pratyayasya, 1.3.7 cuṭū, 1.3.8 laśakvataddhite)
        if morpheme_type == "pratyaya" and len(base) > 0:
            first = base[0]
            if first in {'z'}: # ṣ
                it_markers.add(first)
                base = base[1:]
            elif first in {'c', 'C', 'j', 'J', 'Y', 'w', 'W', 'q', 'Q', 'R'}: # cuṭū
                it_markers.add(first)
                base = base[1:]
            elif first in {'l', 'S', 'k', 'K', 'g', 'G', 'N'}: # laśakva
                it_markers.add(first)
                base = base[1:]

        # 3. Initial root markers (1.3.5 ādiñṭuḍavaḥ)
        if morpheme_type == "root" and len(base) >= 2:
            if base.startswith("YI") or base.startswith("wu") or base.startswith("qu"):
                it_markers.add(base[:2])
                base = base[2:]

        # Compute boolean flags
        flags = MorphemeFlags()
        if 'R' in it_markers or 'Y' in it_markers:
            flags.vriddhi_trigger = True
        if 'k' in it_markers or 'N' in it_markers:
            flags.guna_prohibited = True
        if 'c' in it_markers:
            flags.final_accent = True
        if 'n' in it_markers or 'N' in it_markers:
            flags.initial_accent = True
        if 'S' in it_markers:
            flags.sarvadhatuka_prohibited = False # Śit marks Sārvadhātuka

        return ParsedMorpheme(raw=raw, base=base, it_markers=it_markers, flags=flags, morpheme_type=morpheme_type)

    @staticmethod
    def _is_consonant(char: str) -> bool:
        from core.phonology import CONSONANTS
        return char in CONSONANTS
