"""
Unified Sanskrit Compiler Facade API.
"""

from typing import List, Tuple, Dict, Any
from morphology.sandhi import SandhiEngine
from morphology.subanta import SubantaGenerator
from morphology.tinanta import TinantaGenerator
from core.phonology import slp1_to_iast, iast_to_slp1, slp1_to_devanagari


class SanskritCompiler:
    """End-to-end Pāṇinian compilation engine."""

    @staticmethod
    def join_words(left_iast: str, right_iast: str, output_encoding: str = "iast", is_samasa: bool = False) -> str:
        """Join two words using Sandhi rules."""
        l_slp = iast_to_slp1(left_iast)
        r_slp = iast_to_slp1(right_iast)
        
        # Apply supo dhātuprātipadikayoḥ (2.4.71) for Samāsa via database inversion
        if is_samasa:
            l_slp = SubantaGenerator.get_stem(l_slp)
                
        res_slp = SandhiEngine.join(l_slp, r_slp)

        if output_encoding == "devanagari":
            return slp1_to_devanagari(res_slp)
        return slp1_to_iast(res_slp)

    @staticmethod
    def split_word(continuous_iast: str) -> List[Tuple[str, str]]:
        """Split a continuous sandhi string into possible constituent pairs."""
        c_slp = iast_to_slp1(continuous_iast)
        splits = SandhiEngine.split(c_slp)
        return [(slp1_to_iast(l), slp1_to_iast(r)) for l, r in splits]

    @staticmethod
    def decline_noun(stem_iast: str, case: str, number: str) -> str:
        """Decline a noun stem."""
        stem_slp = iast_to_slp1(stem_iast)
        res_slp = SubantaGenerator.decline(stem_slp, case, number)
        return slp1_to_iast(res_slp)

    @staticmethod
    def conjugate_verb(root_iast: str, gana: int, lakara: str, purusa: int, vacana: int) -> str:
        """Conjugate a verb root."""
        root_slp = iast_to_slp1(root_iast)
        res_slp = TinantaGenerator.conjugate(root_slp, gana, lakara, purusa, vacana)
        return slp1_to_iast(res_slp)
