"""
Immutable Derivation Lineage DAG Token.

Solves the Pāṇinian Sthānivadbhāva problem (1.1.56 sthānivad ādeśo 'nalvidhau)
by preserving the full ancestry graph of string rewrites. Grammatical rules query
the entire ancestry lineage, while phonetic rules query only leaf surface strings.
"""

from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional, Callable, Any


@dataclass
class DagToken:
    """An immutable node in the Sanskrit derivation lineage graph."""
    phonemes: str                               # Surface string (SLP1)
    parents: List['DagToken'] = field(default_factory=list) # Replaced operands (sthānis)
    rule_id: Optional[str] = None               # Sūtra ID that generated this node
    tags: Set[str] = field(default_factory=set) # Structural tags: {'root', 'anga', 'sup', 'tin', 'pada'}
    features: Dict[str, Any] = field(default_factory=dict) # Grammatical features: {'case': 'loc', 'number': 'sg'}
    it_markers: Set[str] = field(default_factory=set) # Preserved IT markers
    consumed_rules: Set[str] = field(default_factory=set) # Rule IDs already fired on this token

    def sthanivad_matches(self, predicate: Callable[['DagToken'], bool], anal_vidhi: bool = False) -> bool:
        """
        Check if this token or any of its ancestors satisfy the predicate.

        Args:
            predicate: Function evaluating a DagToken.
            anal_vidhi: If True (strictly phonetic rule), ignores ancestry (implements 1.1.56 exception).
        """
        if anal_vidhi:
            return predicate(self)

        visited: Set[int] = set()
        queue: List[DagToken] = [self]

        while queue:
            curr = queue.pop(0)
            node_id = id(curr)
            if node_id in visited:
                continue
            visited.add(node_id)

            if predicate(curr):
                return True

            queue.extend(curr.parents)

        return False

    def mutate(
        self,
        new_phonemes: str,
        rule_id: str,
        add_tags: Optional[Set[str]] = None,
        add_features: Optional[Dict[str, Any]] = None,
        extra_parents: Optional[List['DagToken']] = None
    ) -> 'DagToken':
        """
        Return a new DagToken wrapping self (and any extra_parents) as parents.
        """
        merged_parents = [self]
        if extra_parents:
            merged_parents.extend(extra_parents)

        new_tags = set(self.tags)
        if add_tags:
            new_tags.update(add_tags)

        new_features = dict(self.features)
        if add_features:
            new_features.update(add_features)

        new_consumed = set(self.consumed_rules)
        new_consumed.add(rule_id)

        # Merge IT markers from parents
        merged_it = set(self.it_markers)
        if extra_parents:
            for p in extra_parents:
                merged_it.update(p.it_markers)

        return DagToken(
            phonemes=new_phonemes,
            parents=merged_parents,
            rule_id=rule_id,
            tags=new_tags,
            features=new_features,
            it_markers=merged_it,
            consumed_rules=new_consumed
        )

    @property
    def is_elided(self) -> bool:
        """True if this token was deleted (Lopa)."""
        return len(self.phonemes) == 0

    def __repr__(self) -> str:
        tag_str = ",".join(sorted(self.tags)) if self.tags else ""
        return f"DagToken('{self.phonemes}' [{tag_str}])"
