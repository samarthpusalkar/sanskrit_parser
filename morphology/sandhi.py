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
        from compiler.pipeline import PratyaharaResolver
        engine = UniversalRuleEngine.get_instance()
        res_l, res_r = engine.dispatch_forward(w1, w2)
        def _is_vowel_or_pluta(c: str) -> bool:
            return c == '3' or PratyaharaResolver.contains("aC", c)
        if res_l and res_r and (_is_vowel_or_pluta(res_l[-1]) or res_l.endswith('3')) and _is_vowel_or_pluta(res_r[0]):
            return res_l + " " + res_r
        return res_l + res_r

    @classmethod
    def join_with_metadata(cls, w1: str, w2: str) -> dict:
        """Forward sandhi joining with derivation evidence for benchmarking."""
        if not w1:
            return {"joined": w2, "left": "", "right": w2, "applied_rule_ids": [], "trace": {"steps": []}}
        if not w2:
            return {"joined": w1, "left": w1, "right": "", "applied_rule_ids": [], "trace": {"steps": []}}

        from rules.engine import UniversalRuleEngine
        from compiler.pipeline import PratyaharaResolver

        engine = UniversalRuleEngine.get_instance()
        meta = engine.dispatch_forward_with_metadata(w1, w2)
        res_l = meta["left"]
        res_r = meta["right"]

        def _is_vowel_or_pluta(c: str) -> bool:
            return c == '3' or PratyaharaResolver.contains("aC", c)

        joined = res_l + res_r
        if res_l and res_r and (_is_vowel_or_pluta(res_l[-1]) or res_l.endswith('3')) and _is_vowel_or_pluta(res_r[0]):
            joined = res_l + " " + res_r

        meta["joined"] = joined
        return meta

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
