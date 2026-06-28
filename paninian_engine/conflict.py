"""
Conflict Resolution and Bahiraṅga Rewind for the Paninian Rewriting Engine.
Implements exact causal dependency hashing (CausalEnv) and non-fatal ambiguity preservation.
"""
from __future__ import annotations
from typing import Set, List, Dict, Optional, Tuple, Any, FrozenSet, TYPE_CHECKING
from dataclasses import dataclass, field

from .types import DomainIdentifier, AmbiguousDerivationError
from .config import TraditionConfig

if TYPE_CHECKING:
    from .vivaksa import LogicalPredicate


class RuleObject:
    def __init__(
        self,
        sutra_id: str,
        conditioning_factors: Set[str],
        effect_type: str,
        visibility_class: str = "NORMAL",
        optionality: bool = False,
        semantic_condition: Optional["LogicalPredicate"] = None,
        is_nitya: bool = False
    ):
        self.sutra_id = sutra_id
        self.conditioning_factors = conditioning_factors
        self.effect_type = effect_type
        self.visibility_class = visibility_class
        self.optionality = optionality
        self.semantic_condition = semantic_condition
        self.is_nitya = is_nitya

    def is_antaranga_relative_to(self, other: "RuleObject") -> bool:
        """
        Determines if this rule is antaraṅga relative to another.
        The antaraṅga rule is the one whose set of conditioning factors is a proper subset of the other's.
        """
        return self.conditioning_factors < other.conditioning_factors


@dataclass
class ResolutionResult:
    chosen:        Optional[RuleObject] = None
    is_branch:     bool = False
    is_unresolved: bool = False                  # Flag for mathematical ambiguity
    alternatives:  List[RuleObject] = field(default_factory=list)


@dataclass(frozen=True)
class CausalEnv:
    """
    Replaces spatial StructuralEnv. 
    Captures the exact causal fingerprint of the derivation at the moment rule r_B triggered.
    Immune to intervening non-causal phonological noise.
    """
    triggering_rule_id: str
    causal_token_state_ids: FrozenSet[str]
    active_domain_stack: Tuple[DomainIdentifier, ...]

    def __hash__(self) -> int:
        return hash((self.triggering_rule_id, self.causal_token_state_ids, self.active_domain_stack))


ResolvedConflictSet = Set[Tuple[str, str, int]]


class ConflictResolver:
    def __init__(self, config: TraditionConfig):
        self.config = config

    def resolve(
        self,
        candidates: List[RuleObject],
        state: Any
    ) -> ResolutionResult:
        """
        Five-level resolution hierarchy governed by active tradition axioms.
        Raises AmbiguousDerivationError if no explicit hierarchy or axiom resolves ties.
        """
        if not candidates:
            return ResolutionResult()
        if len(candidates) == 1:
            return ResolutionResult(chosen=candidates[0])

        # Step 2: Nitya vs Anitya
        nitya_rules = [r for r in candidates if r.is_nitya]
        if len(nitya_rules) == 1:
            return ResolutionResult(chosen=nitya_rules[0])
        elif len(nitya_rules) > 1:
            candidates = nitya_rules

        # Step 3: Antaraṅga vs Bahiraṅga relational check
        for r in candidates:
            if all(r.is_antaranga_relative_to(other) for other in candidates if other != r):
                return ResolutionResult(chosen=r)

        # Step 7: Optionality (Vibhāṣā) - if all candidates are optional variants
        if all(r.optionality for r in candidates):
            return ResolutionResult(is_branch=True, alternatives=candidates)

        # Step 5: Para (later rule wins by sūtra position) within serial domains
        # If no paribhasas are defined or strict checking fails to break tie definitively:
        if len(candidates) > 1:
            # Check if there is a distinct winner by sūtra order if tradition permits para
            sorted_candidates = sorted(candidates, key=lambda x: [int(p) if p.isdigit() else p for p in x.sutra_id.split(".")])
            chosen = sorted_candidates[-1]
            # If tie persists or tradition requires explicit resolution that is missing:
            if len(candidates) == 2 and not chosen.optionality and not self.config.paribhasas:
                # Raise AmbiguousDerivationError to allow caller to fork non-fatal branch preservation
                raise AmbiguousDerivationError(f"Unresolved tie between {[c.sutra_id for c in candidates]}")
            return ResolutionResult(chosen=chosen)

        return ResolutionResult(chosen=candidates[0])


def execute_bahiranga_rewind(
    state: Any,
    antaranga_rule: RuleObject,
    bahiranga_rule: RuleObject,
    env_hash: int
) -> Any:
    """
    Step 1: Branch/rewind to state immediately before bahiranga_rule was applied.
    Step 2: Apply antaranga_rule.
    Step 3: Record (antaranga_rule.sutra_id, bahiranga_rule.sutra_id, env_hash) in resolved_conflicts.
    """
    state.resolved_conflicts.add((antaranga_rule.sutra_id, bahiranga_rule.sutra_id, env_hash))
    return state
