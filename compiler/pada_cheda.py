"""
Pada-cheda Analytical Parser.

Translates analytical word tags from Ashtadhyayi database ('pc' field)
into structured PadaToken instances with classical case and number physics.
"""

from dataclasses import dataclass
from typing import List, Optional
from core.phonology import devanagari_to_slp1


@dataclass
class PadaToken:
    devanagari: str
    slp1: str
    category: str
    case: Optional[int]
    number: Optional[int]

    @property
    def is_target(self) -> bool:
        """Pāṇini 1.1.49: ṣaṣṭhī sthāneyogā (Genitive / 6th case denotes Sthānin)."""
        return self.case == 6

    @property
    def is_substitute(self) -> bool:
        """Nominative / 1st case denotes Ādeśa or Sañjñā result."""
        return self.case == 1

    @property
    def is_right_context(self) -> bool:
        """Pāṇini 1.1.66: tasminniti nirdiṣṭe pūrvasya (Locative / 7th case denotes right context)."""
        return self.case == 7

    @property
    def is_left_context(self) -> bool:
        """Pāṇini 1.1.67: tasmādityuttarasya (Ablative / 5th case denotes left context)."""
        return self.case == 5

    @property
    def is_augment(self) -> bool:
        """Instrumental / 3rd case denotes Āgama."""
        return self.case == 3


class PadaChedaParser:
    """Parses raw analytical Pada-cheda ('pc') tags from Ashtadhyayi database."""

    @classmethod
    def parse(cls, pc_string: str) -> List[PadaToken]:
        if not pc_string or pc_string.strip() == "":
            return []

        tokens = []
        raw_chunks = pc_string.split("##")
        for chunk in raw_chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            parts = chunk.split("$")
            surface_dev = parts[0]
            cat = parts[1] if len(parts) > 1 else ""

            raw_case = parts[2] if len(parts) > 2 else ""
            raw_num = parts[3] if len(parts) > 3 else ""

            case_val = int(raw_case) if raw_case.isdigit() else None
            num_val = int(raw_num) if raw_num.isdigit() else None

            slp1_str = devanagari_to_slp1(surface_dev)

            tokens.append(PadaToken(
                devanagari=surface_dev,
                slp1=slp1_str,
                category=cat,
                case=case_val,
                number=num_val
            ))

        return tokens
