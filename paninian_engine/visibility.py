"""
Causal Visibility for the Paninian Context-Dependent Rewriting Engine.
Implements memory-safe state forking via PersistentVisibilityMatrix using pyrsistent.
"""
from __future__ import annotations
from typing import Dict, FrozenSet, Optional, Tuple
from dataclasses import dataclass
from pyrsistent import pmap, PMap

from .types import DomainIdentifier


@dataclass(frozen=True)
class VisibilityMask:
    visible_rule_ids: FrozenSet[str]

    def is_visible(self, rule_id: str) -> bool:
        return rule_id in self.visible_rule_ids


class PersistentVisibilityMatrix:
    """
    Persistent causal visibility matrix V ∈ {0,1}^(n×n).
    Instead of cloning an n×n matrix on every BFS branch fork, child states
    maintain an immutable sparse map of suspended causal links:
       (evaluating_idx, caused_by_idx) -> 0
    Unmapped pairs default to 1 (causally visible).
    This ensures O(1) state forking across BFS queues.
    """
    def __init__(self, suspensions: Optional[PMap[Tuple[int, int], int]] = None):
        self._suspensions = suspensions if suspensions is not None else pmap()

    def mask(self, evaluating_rule_idx: int, caused_by_rule_idx: int) -> PersistentVisibilityMatrix:
        """Returns a NEW persistent matrix instance with the causal suspension added in O(1)."""
        new_suspensions = self._suspensions.set((evaluating_rule_idx, caused_by_rule_idx), 0)
        return PersistentVisibilityMatrix(new_suspensions)

    def is_visible(self, evaluating_idx: int, caused_by_idx: int) -> bool:
        return self._suspensions.get((evaluating_idx, caused_by_idx), 1) == 1

    def visibility_mask_for(
        self,
        rule_idx: int,
        total_rules_applied: int,
        rule_id_map: Dict[int, str]
    ) -> VisibilityMask:
        """
        Projects the k-th row of V into a VisibilityMask for rule r_k.
        Every call to compute_samjna or trigger evaluation receives this projection.
        """
        visible_ids = {
            rule_id_map[j]
            for j in range(total_rules_applied)
            if j in rule_id_map and self.is_visible(rule_idx, j)
        }
        return VisibilityMask(visible_rule_ids=frozenset(visible_ids))


# Alias for compatibility with earlier tests
CausalVisibilityMatrix = PersistentVisibilityMatrix


class AsiddhaDomainPolicy:
    def __init__(self, domain: DomainIdentifier, regime: str, scope_start: str, scope_end: str):
        self.domain = domain
        self.regime = regime       # 'PURVATRA', 'ASIDDHAVAT', 'BAHIRANGA'
        self.scope_start = scope_start
        self.scope_end = scope_end

    def applies_between(self, evaluating_rule_id: str, prior_rule_id: str) -> bool:
        """
        Returns True if prior_rule_id is causally suspended for evaluating_rule_id.
        """
        if self.regime == "PURVATRA":
            return prior_rule_id > evaluating_rule_id
        elif self.regime == "ASIDDHAVAT":
            return self.scope_start <= prior_rule_id <= self.scope_end and self.scope_start <= evaluating_rule_id <= self.scope_end
        elif self.regime == "BAHIRANGA":
            return True
        return False
