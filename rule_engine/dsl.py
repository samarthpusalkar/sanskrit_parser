"""
Declarative JSON Sūtra AST DSL Specification.

Enforces that every Pāṇinian rule is pure data (not arbitrary code).
Enables mechanical invertibility, rule introspection, and formal verification.
"""

from dataclasses import dataclass, field
from typing import Dict, Set, Optional, Any, List, Union
from vm.token import DagToken
from core.shiva_sutras import PratyaharaResolver


@dataclass
class ConditionSpec:
    """Predicate condition matching on phonetic context or ancestry lineage."""
    pratyahara: Optional[str] = None           # e.g. 'iK', 'aC', 'haL'
    exact_text: Optional[str] = None           # e.g. 'gam', 'ha'
    tokens_required: Optional[Set[str]] = None # e.g. {'pra', 'upa', 'ava'}
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
class PrimitiveOp:
    """
    Universal operation primitive. Every Pāṇinian operation decomposes to:
    - Remove last `left_consume` chars from left boundary
    - Remove first `right_consume` chars from right boundary
    - Insert `emit` string on `emit_side` ('left' or 'right')
    - If `compute_fn` is set, compute the emit value dynamically

    compute_fn is a CLOSED set from Pāṇini's finite operation vocabulary:
    NULL, 'guna', 'vriddhi', 'dirgha', 'savarna_long', 'bijection', 'natva', 'shatva'
    """
    left_consume: int = 0
    right_consume: int = 0
    emit: str = ""
    emit_side: str = "left"         # 'left' or 'right'
    compute_fn: Optional[str] = None  # NULL, 'guna', 'vriddhi', 'dirgha', 'savarna_long', 'bijection', 'natva', 'shatva'
    # Kept for bijection resolution and revert compatibility
    substitute: Optional[str] = None
    op_type: Optional[str] = None   # legacy label, kept for revert index

    @classmethod
    def from_legacy(cls, op_type: str, substitute: Optional[str] = None) -> 'PrimitiveOp':
        """Convert old op_type + substitute string into universal primitives."""
        sub = substitute or ""
        mapping = {
            "elide":                    (1, 0, "",    "left",  None),
            "substitute":               (1, 0, sub,   "left",  None),
            "exact_substitute":         (1, 0, sub,   "left",  None),
            "insert":                   (0, 0, sub,   "left",  None),
            "merge":                    (1, 1, sub,   "left",  None),
            "purva_rupa":               (0, 1, "'",   "right", None),
            "pararupa":                 (1, 0, "",    "left",  None),
            "visarga_utva":             (2, 0, "o",   "left",  None),
            "anusvara":                 (1, 0, "M",   "left",  None),
            "right_substitute":         (0, 1, sub,   "right", None),
            "right_prepend":            (0, 0, sub,   "right", None),
            "prakritibhava":            (0, 0, "",    "left",  None),
            "non_operational":          (0, 0, "",    "left",  None),
            "external_block":           (0, 0, "",    "left",  None),
            "governance":               (0, 0, "",    "left",  None),
            "prohibit":                 (0, 0, "",    "left",  None),
            # Computed operations
            "dirgha":                   (1, 1, "",    "left",  "dirgha"),
            "ekadesha_savarna_dirgha":  (1, 1, "",    "left",  "dirgha"),
            "merge_savarna":            (1, 1, "",    "left",  "dirgha"),
            "ekadesha_guna":            (1, 1, "",    "left",  "guna"),
            "ekadesha_vriddhi":         (1, 1, "",    "left",  "vriddhi"),
            "ro_ri_dirgha":             (2, 0, "",    "left",  "savarna_long"),
            "dhra_lopa_dirgha":         (2, 0, "",    "left",  "savarna_long"),
            "bijection_substitute":     (1, 0, sub,   "left",  "bijection"),
            "bijection_right_substitute": (0, 1, sub, "right", "bijection"),
            "natva":                    (0, 0, "",    "left",  "natva"),
            "shatva":                   (0, 0, "",    "left",  "shatva"),
        }
        # Handle sanjna_substitute by checking the substitute value
        if op_type == "sanjna_substitute":
            if sub == "guna":
                lc, rc, em, es, cf = (1, 1, "", "left", "guna")
            elif sub == "vriddhi":
                lc, rc, em, es, cf = (1, 1, "", "left", "vriddhi")
            elif sub == "dirgha":
                lc, rc, em, es, cf = (1, 1, "", "left", "dirgha")
            else:
                lc, rc, em, es, cf = (1, 0, sub, "left", None)
        else:
            lc, rc, em, es, cf = mapping.get(op_type, (1, 0, sub, "left", None))

        return cls(
            left_consume=lc, right_consume=rc,
            emit=em, emit_side=es, compute_fn=cf,
            substitute=substitute, op_type=op_type
        )


@dataclass
class OperationSpec:
    """Surgical string modification command (legacy, kept for backward compat)."""
    op_type: str                               # 'substitute', 'augment', 'elide', 'merge_sandhi'
    substitute: Optional[str] = None           # Exact str, or 'guna', 'vriddhi', 'dirgha', or pratyahara 'yaṆ'
    augment: Optional[str] = None
    position: str = "in_place"                 # 'before', 'after', 'in_place'

    def to_primitive(self) -> 'PrimitiveOp':
        """Convert this legacy spec to a universal primitive."""
        return PrimitiveOp.from_legacy(self.op_type, self.substitute)

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
    operation: Union[OperationSpec, PrimitiveOp] = field(default_factory=lambda: OperationSpec("substitute"))
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
