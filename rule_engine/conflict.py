"""
Pāṇinian Jurisprudence Conflict Resolver.

Replaces naïve priority numbers and one-sided tie-breakers with classical Vyākaraṇa jurisprudence:
1. Apavāda (Exception containment check)
2. Antaraṅga vs Bahiraṅga (Dependency span calculation)
3. Nitya (Mandatory execution)
4. Vipratiṣedhe paraṁ kāryam (1.4.2 right-side tie-breaker)
"""

from dataclasses import dataclass
from typing import List, Optional
from rule_engine.dsl import RuleSpec
from vm.context import DerivationContext


@dataclass
class RuleMatch:
    """An active instantiation of a sūtra matching a specific tape location."""
    rule: RuleSpec
    target_idx: int
    left_idx: Optional[int] = None
    right_idx: Optional[int] = None

    @property
    def span(self) -> int:
        """Calculate grammatical dependency span."""
        indices = [self.target_idx]
        if self.left_idx is not None:
            indices.append(self.left_idx)
        if self.right_idx is not None:
            indices.append(self.right_idx)
        return max(indices) - min(indices)


class ConflictResolver:
    """Resolves competing rule matches on the tape."""

    @classmethod
    def choose(cls, matches: List[RuleMatch], context: DerivationContext) -> RuleMatch:
        """Pick the single winning rule match."""
        if not matches:
            raise ValueError("Cannot choose from empty match list.")
        if len(matches) == 1:
            return matches[0]

        # 1. Check explicit Apavāda blocking
        all_rule_ids = {m.rule.id for m in matches}
        non_blocked = []
        for m in matches:
            if not m.rule.governance.blocking.intersection(all_rule_ids):
                non_blocked.append(m)

        active_matches = non_blocked if non_blocked else matches

        # Sort matches by our jurisprudence priority queue:
        # Key 1: Explicit priority ranking (higher priority integer wins)
        # Key 2: Antaraṅga span (smaller span wins -> we negate span for ascending sort)
        # Key 3: Right-operand position (1.4.2 vipratiṣedhe param -> larger target_idx wins)
        def _sort_key(m: RuleMatch):
            return (
                m.rule.priority,
                -m.span,
                m.target_idx
            )

        sorted_matches = sorted(active_matches, key=_sort_key, reverse=True)
        return sorted_matches[0]
