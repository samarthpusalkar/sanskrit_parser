"""
Nominal Declension Generator (Subanta).

Generates noun cases across 8 cases × 3 numbers by attaching SuP affixes
and running the Pāṇinian VM.
"""

from typing import Dict, List, Tuple
from vm.token import DagToken
from vm.context import DerivationContext
from morphology.sandhi import SandhiEngine


SUP_TABLE_A_STEM: Dict[Tuple[str, str], str] = {
    ("nominative", "singular"): "s",
    ("nominative", "dual"): "O",
    ("nominative", "plural"): "as",
    ("accusative", "singular"): "am",
    ("accusative", "dual"): "O",
    ("accusative", "plural"): "as",
    ("instrumental", "singular"): "ena",
    ("instrumental", "dual"): "ByAm",
    ("instrumental", "plural"): "Eḥ",
    ("dative", "singular"): "Aya",
    ("dative", "dual"): "ByAm",
    ("dative", "plural"): "eByaḥ",
    ("ablative", "singular"): "At",
    ("ablative", "dual"): "ByAm",
    ("ablative", "plural"): "eByaḥ",
    ("genitive", "singular"): "asya",
    ("genitive", "dual"): "ayoḥ",
    ("genitive", "plural"): "AnAm",
    ("locative", "singular"): "e",
    ("locative", "dual"): "ayoḥ",
    ("locative", "plural"): "ezu",
    ("vocative", "singular"): "",
    ("vocative", "dual"): "O",
    ("vocative", "plural"): "as"
}


class SubantaGenerator:
    @classmethod
    def decline(cls, stem_slp1: str, case: str, number: str) -> str:
        """
        Decline a nominal stem.

        Example: decline("rAma", "locative", "singular") -> "rAme"
        """
        # For our starter compiler demonstrator, resolve a-stem endings
        # In full 4000 sutras, SUP_TABLE is raw 'su, au, jas...' and sūtras mutate 'a+i -> e'
        raw_suffix = SUP_TABLE_A_STEM.get((case.lower(), number.lower()), "")

        if not raw_suffix:
            return stem_slp1

        # Run through Sandhi engine to blend boundary
        if raw_suffix in {"s", "H"}:
            return stem_slp1 + "H"
        if raw_suffix.startswith("e") or raw_suffix.startswith("A") or raw_suffix.startswith("E") or raw_suffix.startswith("O"):
            # Direct pre-blended ending in simplified table
            return stem_slp1[:-1] + raw_suffix if stem_slp1.endswith("a") else stem_slp1 + raw_suffix

        return SandhiEngine.join(stem_slp1, raw_suffix)
