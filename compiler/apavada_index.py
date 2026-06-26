"""
Apavāda Containment Indexer.

Computes Utsarga-Apavāda domain subset mathematical relationships across Sūtra predicates.
An Apavāda exception rule automatically suppresses its Utsarga general rule.
"""

from typing import List, Dict, Set
from rule_engine.dsl import RuleSpec
from core.shiva_sutras import PratyaharaResolver


class ApavadaIndexer:
    """Computes Utsarga-Apavāda domain subset hierarchy."""

    @staticmethod
    def compute_domain_phonemes(rule: RuleSpec) -> frozenset:
        target = rule.target_context
        if target.exact_text:
            return frozenset(target.exact_text.split(","))
        if target.pratyahara:
            return PratyaharaResolver.resolve(target.pratyahara)
        return frozenset()

    @classmethod
    def build_hierarchy(cls, rules: List[RuleSpec]) -> Dict[str, List[str]]:
        """
        Returns map of general_rule_id -> List[apavada_rule_ids]
        where apavada domain is strict non-empty subset of general domain.
        """
        hierarchy: Dict[str, List[str]] = {r.id: [] for r in rules}
        domains = {r.id: cls.compute_domain_phonemes(r) for r in rules}

        for i, r1 in enumerate(rules):
            dom1 = domains[r1.id]
            if not dom1:
                continue
            for j, r2 in enumerate(rules):
                if i == j:
                    continue
                dom2 = domains[r2.id]
                if not dom2:
                    continue
                # If dom2 is strict subset of dom1
                if dom2 < dom1:
                    hierarchy[r1.id].append(r2.id)

        return hierarchy
