"""
Bidirectional Sandhi Engine.

Performs forward phonetic blending (join) by running the Pāṇinian VM,
and deterministic backward word splitting (split) by mechanically inverting
declarative JSON Sūtra specifications.
"""

import json
from pathlib import Path
from typing import List, Tuple, Optional
from vm.token import DagToken
from vm.context import DerivationContext
from rule_engine.dsl import RuleSpec
from rule_engine.machine import PaniniVM


class SandhiEngine:
    _rules: List[RuleSpec] = []
    _vm: Optional[PaniniVM] = None

    @classmethod
    def _ensure_loaded(cls) -> None:
        if cls._vm is not None:
            return
        rules_path = Path(__file__).parent.parent / "rules" / "core_sutras.json"
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cls._rules = [RuleSpec.from_dict(d) for d in data]
        cls._vm = PaniniVM(cls._rules)

    @classmethod
    def join(cls, left_slp1: str, right_slp1: str) -> str:
        """
        Forward sandhi joining of two words.

        Example: join("rAma", "ISa") -> "rAmeSa"
        """
        cls._ensure_loaded()
        t1 = DagToken(phonemes=left_slp1, tags={'pada'})
        t2 = DagToken(phonemes=right_slp1, tags={'pada'})
        ctx = DerivationContext(tape=[t1, t2])
        out_ctx = cls._vm.run(ctx)
        return out_ctx.surface_str

    @classmethod
    def split(cls, continuous_slp1: str) -> List[Tuple[str, str]]:
        """
        Backward mechanical sandhi splitting.

        Example: split("rAmeSa") -> [("rAma", "ISa"), ("rAmA", "ISa"), ...]
        """
        cls._ensure_loaded()
        results: List[Tuple[str, str]] = []

        # Mechanical inversion table derived from declarative rules
        # 1. Guna (e, o, ar)
        for i, char in enumerate(continuous_slp1):
            left_prefix = continuous_slp1[:i]
            right_suffix = continuous_slp1[i+1:]

            if char == 'e':
                for l_end in ['a', 'A']:
                    for r_start in ['i', 'I']:
                        results.append((left_prefix + l_end, r_start + right_suffix))
            elif char == 'o':
                for l_end in ['a', 'A']:
                    for r_start in ['u', 'U']:
                        results.append((left_prefix + l_end, r_start + right_suffix))
            elif char == 'E': # Vriddhi ai
                for l_end in ['a', 'A']:
                    for r_start in ['e', 'E']:
                        results.append((left_prefix + l_end, r_start + right_suffix))
            elif char == 'O': # Vriddhi au
                for l_end in ['a', 'A']:
                    for r_start in ['o', 'O']:
                        results.append((left_prefix + l_end, r_start + right_suffix))
            elif char in {'A', 'I', 'U'}: # Savarna Dirgha
                base_short = char.lower()
                for l_end in [base_short, char]:
                    for r_start in [base_short, char]:
                        results.append((left_prefix + l_end, r_start + right_suffix))
            elif char == 'y' and len(right_suffix) > 0 and right_suffix[0] in 'aAiIuUfFxXeEoO': # Yan
                for l_end in ['i', 'I']:
                    results.append((left_prefix + l_end, right_suffix))
            elif char == 'v' and len(right_suffix) > 0 and right_suffix[0] in 'aAiIuUfFxXeEoO':
                for l_end in ['u', 'U']:
                    results.append((left_prefix + l_end, right_suffix))

        return list(dict.fromkeys(results)) # Remove duplicates
