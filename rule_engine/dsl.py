"""
Declarative JSON Sūtra AST DSL Specification.

Enforces that every Pāṇinian rule is pure data (not arbitrary code).
Enables mechanical invertibility, rule introspection, and formal verification.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Any, List
from vm.token import DagToken
from core.shiva_sutras import PratyaharaResolver


@dataclass
class ConditionSpec:
    """Predicate condition matching on phonetic context or ancestry lineage."""
    pratyahara: Optional[str] = None           # e.g. 'iK', 'aC', 'haL'
    exact_text: Optional[str] = None           # e.g. 'gam', 'ha'
    tags_required: Set[str] = field(default_factory=set) # e.g. {'root'}
    features_required: Dict[str, Any] = field(default_factory=dict)
    it_required: Optional[str] = None
    anal_vidhi: bool = False                   # If True, strictly checks leaf phonemes
    match_pos: str = "end"                     # 'end' checks last char, 'start' checks first char
    savarna_with_target: bool = False          # If True, enforces 1.1.9 homogeneous match

    def matches(self, token: DagToken) -> bool:
        """Evaluate if token satisfies this condition."""
        if token.is_elided:
            return False

        if not token.phonemes:
            return False
        char_to_check = token.phonemes[0] if self.match_pos == "start" else token.phonemes[-1]

        # 1. Exact boundary phoneme or entire token match
        if self.exact_text is not None:
            allowed = set(self.exact_text.split(","))
            if char_to_check not in allowed and token.phonemes != self.exact_text:
                return False

        # 2. Pratyāhāra match (checks boundary phoneme)
        if self.pratyahara is not None:
            if not PratyaharaResolver.contains(self.pratyahara, char_to_check):
                return False

        # 3. Tags & Features via Sthānivadbhāva ancestry
        def _check_meta(node: DagToken) -> bool:
            if self.tags_required and not self.tags_required.issubset(node.tags):
                return False
            if self.features_required:
                for k, v in self.features_required.items():
                    if node.features.get(k) != v:
                        return False
            if self.it_required and self.it_required not in node.it_markers:
                return False
            return True

        if self.tags_required or self.features_required or self.it_required:
            if not token.sthanivad_matches(_check_meta, anal_vidhi=self.anal_vidhi):
                return False

        return True

    @classmethod
    def from_dict(cls, data: Dict[str, Any], default_pos: str = "end") -> 'ConditionSpec':
        return cls(
            pratyahara=data.get("pratyahara"),
            exact_text=data.get("exact_text"),
            tags_required=set(data.get("tags_required", [])),
            features_required=data.get("features_required", {}),
            it_required=data.get("it_required"),
            anal_vidhi=data.get("anal_vidhi", False),
            match_pos=data.get("match_pos", default_pos),
            savarna_with_target=data.get("savarna_with_target", False)
        )


@dataclass
class OperationSpec:
    """Surgical string modification command."""
    op_type: str                               # 'substitute', 'augment', 'elide', 'merge_sandhi'
    substitute: Optional[str] = None           # Exact str, or 'guna', 'vriddhi', 'dirgha', or pratyahara 'yaṆ'
    augment: Optional[str] = None
    position: str = "in_place"                 # 'before', 'after', 'in_place'

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OperationSpec':
        return cls(
            op_type=data.get("op_type", "substitute"),
            substitute=data.get("substitute"),
            augment=data.get("augment"),
            position=data.get("position", "in_place")
        )


@dataclass
class GovernanceSpec:
    """Domain scope, governing headers, and blocking constraints."""
    domain: str = "sapada"                     # 'sapada' (1.1-8.1), 'tripadi' (8.2-8.4), 'abhiya' (6.4)
    adhikaras: Set[str] = field(default_factory=set)
    blocking: Set[str] = field(default_factory=set)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GovernanceSpec':
        return cls(
            domain=data.get("domain", "sapada"),
            adhikaras=set(data.get("adhikaras", [])),
            blocking=set(data.get("blocking", []))
        )


@dataclass
class RuleSpec:
    """Declarative specification of a Pāṇinian sūtra."""
    id: str                                    # e.g. '6.1.77'
    name: str                                  # e.g. 'iko yanaci'
    rule_type: str                             # 'vidhi_sandhi', 'vidhi_anga', 'samjna', 'paribhasha'
    priority: int                              # Base priority (1-1000)
    target_context: ConditionSpec
    left_context: Optional[ConditionSpec] = None
    right_context: Optional[ConditionSpec] = None
    operation: OperationSpec = field(default_factory=lambda: OperationSpec("substitute"))
    governance: GovernanceSpec = field(default_factory=GovernanceSpec)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RuleSpec':
        return cls(
            id=data["id"],
            name=data.get("name", data["id"]),
            rule_type=data.get("rule_type", "vidhi"),
            priority=data.get("priority", 100),
            target_context=ConditionSpec.from_dict(data["target_context"], "end"),
            left_context=ConditionSpec.from_dict(data["left_context"], "end") if data.get("left_context") else None,
            right_context=ConditionSpec.from_dict(data["right_context"], "start") if data.get("right_context") else None,
            operation=OperationSpec.from_dict(data.get("operation", {})),
            governance=GovernanceSpec.from_dict(data.get("governance", {}))
        )
