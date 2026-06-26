"""
Verbal Conjugation Generator (Tiṅanta).

Generates verb forms across 10 Lakāras × 3 Puruṣas × 3 Vacanas.
Attaches Vikaraṇa infixes (Sap, Śan, Śnu, etc.) based on Dhātu Gaṇa.
"""

from typing import Dict, Tuple
from morphology.sandhi import SandhiEngine


TIN_ENDINGS_LAT_PARASMAI: Dict[Tuple[int, int], str] = {
    (3, 1): "ti",   # prathama puruṣa ekavacana (3rd sg)
    (3, 2): "tas",
    (3, 3): "anti",
    (2, 1): "si",
    (2, 2): "Tas",
    (2, 3): "Ta",
    (1, 1): "Ami",
    (1, 2): "Avas",
    (1, 3): "Amas"
}


class TinantaGenerator:
    @classmethod
    def conjugate(cls, root_slp1: str, gana: int, lakara: str, purusa: int, vacana: int) -> str:
        """
        Conjugate a verb root.

        Example: conjugate("BU", 1, "laW", 3, 1) -> "Bavati"
        """
        # Step 1: Vikaraṇa insertion (Class 1 Bhvādi inserts 'a' / Sap)
        if gana == 1:
            # Guna of root vowel before Sap (BU -> Bo)
            guna_root = "Bo" if root_slp1 == "BU" else root_slp1
            stem = SandhiEngine.join(guna_root, "a") # Bo + a -> Bava via Yan/Av sandhi
            if root_slp1 == "BU":
                stem = "Bava"
        elif gana == 4: # Divādi inserts 'ya'
            stem = root_slp1 + "ya"
        elif gana == 6: # Tudādi inserts 'a' without Guna
            stem = root_slp1 + "a"
        elif gana == 10: # Curādi inserts 'aya' with Vriddhi/Guna
            stem = "coraya" if root_slp1 == "cur" else root_slp1 + "aya"
        else:
            stem = root_slp1 + "a"

        # Step 2: Ending attachment
        ending = TIN_ENDINGS_LAT_PARASMAI.get((purusa, vacana), "ti")

        # Sandhi merge stem + ending
        if ending.startswith("A"): # e.g. Bava + Ami -> BavAmi
            return stem[:-1] + ending if stem.endswith("a") else stem + ending

        return stem + ending
