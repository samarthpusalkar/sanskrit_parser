"""
Universal Pāṇinian Rule Engine Dispatcher and Operational Conflict Resolver.

Manages active sūtra registries, Tripādī ordering rules (8.2.1 - 8.4.68),
and conflict resolution via Paribhāṣās (e.g. 1.4.2 vipratiṣedhe paraṃ kāryam).
"""

from typing import List, Dict, Any, Tuple
from rules.base import PaniniRule, VidhiRule


class UniversalRuleEngine:
    """Master rule engine orchestrating grammatical transformations."""

    def __init__(self, auto_compile: bool = True):
        self._rules: List[PaniniRule] = []
        if auto_compile:
            from compiler.pipeline import MasterCompilerPipeline
            self._rules.extend(MasterCompilerPipeline.compile_all())

    def register_rule(self, rule: PaniniRule):
        self._rules.append(rule)

    def dispatch_forward(self, left: str, right: str, context: Dict[str, Any] = None) -> Tuple[str, str]:
        """Apply sequential forward sandhi/morphological transformation rules."""
        ctx = context or {}
        cur_l, cur_r = left, right
        for r in self._rules:
            if r.matches(cur_l, cur_r, ctx):
                cur_l, cur_r = r.apply(cur_l, cur_r, ctx)
        return cur_l, cur_r

    def dispatch_revert(self, surface: str, context: Dict[str, Any] = None) -> List[Tuple[str, str]]:
        """Compute all possible backward sandhi splits."""
        ctx = context or {}
        splits = []
        for r in self._rules:
            splits.extend(r.revert(surface, ctx))
        return list(set(splits))
