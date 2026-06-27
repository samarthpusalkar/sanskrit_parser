"""
Universal Pāṇinian Rule Engine Dispatcher and Operational Conflict Resolver.

Manages active sūtra registries, Tripādī ordering rules (8.2.1 - 8.4.68),
and conflict resolution via Paribhāṣās (e.g. 1.4.2 vipratiṣedhe paraṃ kāryam).
"""

from typing import List, Dict, Any, Tuple
from rules.base import PaniniRule, VidhiRule


class UniversalRuleEngine:
    """Master rule engine orchestrating grammatical transformations."""

    _instance = None

    @classmethod
    def get_instance(cls) -> 'UniversalRuleEngine':
        if cls._instance is None:
            cls._instance = cls(auto_compile=True)
        return cls._instance

    def __init__(self, auto_compile: bool = True):
        self._rules: List[PaniniRule] = []
        if auto_compile:
            from compiler.pipeline import MasterCompilerPipeline
            self._rules.extend(MasterCompilerPipeline.compile_all())

    def register_rule(self, rule: PaniniRule):
        self._rules.append(rule)

    def _get_sandhi_ordered_rules(self) -> List[PaniniRule]:
        priority_ids = ["6.1.101", "6.1.88", "6.1.87", "6.1.77"]
        p_rules = [r for r in self._rules if r.sutra_id in priority_ids]
        p_rules.sort(key=lambda r: priority_ids.index(r.sutra_id))
        other_sandhi = [r for r in self._rules if r.sutra_id not in priority_ids and r.sutra_id.startswith(("6.1.", "8.2.", "8.3.", "8.4.", "7.2."))]
        rest = [r for r in self._rules if r not in p_rules and r not in other_sandhi]
        return p_rules + other_sandhi + rest

    def dispatch_forward(self, left: str, right: str, context: Dict[str, Any] = None) -> Tuple[str, str]:
        """Apply sequential forward sandhi/morphological transformation rules."""
        ctx = context or {}
        cur_l, cur_r = left, right
        ordered = self._get_sandhi_ordered_rules()
        for r in ordered:
            if r.matches(cur_l, cur_r, ctx):
                new_l, new_r = r.apply(cur_l, cur_r, ctx)
                if new_l != cur_l or new_r != cur_r:
                    return new_l, new_r
        return cur_l, cur_r

    def dispatch_revert(self, surface: str, context: Dict[str, Any] = None) -> List[Tuple[str, str]]:
        """Compute all possible backward sandhi splits."""
        ctx = context or {}
        splits = []
        ordered = self._get_sandhi_ordered_rules()
        for r in ordered:
            splits.extend(r.revert(surface, ctx))
        return list(set(splits))
