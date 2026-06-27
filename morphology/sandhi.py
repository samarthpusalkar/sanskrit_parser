"""
Universal Algorithmic Sandhi Engine.

Delegates forward phonetic joining and backward word splitting directly to the
dynamically compiled Pāṇinian sūtra database via UniversalRuleEngine.
"""

from typing import List, Tuple


class SandhiEngine:
    """Algorithmic Sandhi Engine delegating to UniversalRuleEngine sūtras."""

    @classmethod
    def join(cls, w1: str, w2: str) -> str:
        """Forward sandhi joining via universal sūtras."""
        if not w1: return w2
        if not w2: return w1

        from rules.engine import UniversalRuleEngine
        engine = UniversalRuleEngine.get_instance()
        res_l, res_r = engine.dispatch_forward(w1, w2)
        from core.shiva_sutras import PratyaharaResolver
        from core.phonology import VISARGA_ALLOPHONES
        if res_l and res_r:
            if PratyaharaResolver.contains("aC", res_l[-1]) and PratyaharaResolver.contains("aC", res_r[0]):
                return res_l + " " + res_r
            if w1[-1] in VISARGA_ALLOPHONES and PratyaharaResolver.contains("aC", res_l[-1]) and not res_r.startswith('r'):
                return res_l + " " + res_r
        return res_l + res_r

    @classmethod
    def split(cls, text: str) -> List[Tuple[str, str]]:
        """Backward sandhi splitting via universal sūtra inversions."""
        results: List[Tuple[str, str]] = []
        if not text:
            return results

        from rules.engine import UniversalRuleEngine
        engine = UniversalRuleEngine.get_instance()
        results.extend(engine.dispatch_revert(text))

        # Include basic boundary splits for unmutated concatenation edges
        for i in range(1, len(text)):
            results.append((text[:i], text[i:]))

        return list(dict.fromkeys(results))
