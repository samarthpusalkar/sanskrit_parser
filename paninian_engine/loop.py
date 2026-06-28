"""
Derivation State and Execution Loop for the Paninian Rewriting Engine.
Integrates PersistentVisibilityMatrix, CausalEnv hashing, Śābdabodha injection, and non-fatal ambiguity preservation.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional, FrozenSet
import copy

from .types import DomainType, AmbiguousDerivationError, LexicalCategory, DomainIdentifier
from .config import TraditionConfig
from .visibility import PersistentVisibilityMatrix, AsiddhaDomainPolicy, VisibilityMask
from .conflict import RuleObject, ConflictResolver, ResolvedConflictSet, ResolutionResult, CausalEnv
from .vivaksa import VivaksaAST, SemanticConditionEvaluator, SabdabodhaFrame
from .graph import MorphoPhonemicToken, TokenState, DerivationGraph


@dataclass
class DerivationState:
    tokens:             List[MorphoPhonemicToken]
    applied_rules:      List[Tuple[str, str]] = field(default_factory=list)
    visibility_matrix:  Optional[PersistentVisibilityMatrix] = None
    resolved_conflicts: ResolvedConflictSet = field(default_factory=set)
    domain_stack:       List[AsiddhaDomainPolicy] = field(default_factory=list)
    vivaksa:            Optional[VivaksaAST] = None
    sabdabodha:         Optional[SabdabodhaFrame] = None
    semantic_state:     Dict[str, object] = field(default_factory=dict)
    trace:              List[str] = field(default_factory=list)
    rule_id_map:        Dict[int, str] = field(default_factory=dict)
    rule_id_map_inv:    Dict[str, int] = field(default_factory=dict)
    _domains:           Dict[DomainType, List[Any]] = field(default_factory=dict)

    def domain_for(self, domain_type: DomainType) -> List[Any]:
        res = []
        if self.sabdabodha:
            res.extend(self.sabdabodha.resolve_domain(domain_type))
        res.extend(self._domains.get(domain_type, []))
        return res

    def fork(self) -> "DerivationState":
        """
        Memory-safe state fork.
        Clones token wrappers and lists while sharing the persistent visibility matrix and graph states.
        """
        forked = copy.copy(self)
        forked.tokens = [copy.copy(t) for t in self.tokens]
        forked.applied_rules = list(self.applied_rules)
        forked.trace = list(self.trace)
        forked.resolved_conflicts = set(self.resolved_conflicts)
        forked.rule_id_map = dict(self.rule_id_map)
        forked.rule_id_map_inv = dict(self.rule_id_map_inv)
        # visibility_matrix is PersistentVisibilityMatrix (immutable PMap), so direct sharing is 100% memory safe!
        return forked


def is_eligible(
    rule:      RuleObject,
    state:     DerivationState,
    evaluator: SemanticConditionEvaluator,
    config:    TraditionConfig
) -> bool:
    """
    Evaluates prāpti for this rule against the current derivation state.
    """
    # Check visibility projection
    if rule.sutra_id in state.rule_id_map_inv and state.visibility_matrix:
        rule_idx = state.rule_id_map_inv[rule.sutra_id]
        mask = state.visibility_matrix.visibility_mask_for(rule_idx, len(state.rule_id_map), state.rule_id_map)
    else:
        mask = VisibilityMask(frozenset(state.rule_id_map.values() if state.rule_id_map else [rule.sutra_id]))

    # Semantic condition check (Vivakṣā + Śābdabodha bridge)
    if rule.semantic_condition:
        if not evaluator.eval_condition(state.vivaksa, rule.semantic_condition, state):
            return False

    # Phonological / structural conditioning factors check
    curr_phonemes = {t.graph.get(t.current_state_id).phoneme for t in state.tokens if t.current_state_id in t.graph._states}
    for factor in rule.conditioning_factors:
        if factor not in curr_phonemes and factor not in state.semantic_state:
            return False

    return True


def apply_rule(state: DerivationState, rule: RuleObject) -> DerivationState:
    """
    Applies the chosen rule to create a new derivation state.
    """
    new_state = state.fork()

    # Register rule in rule_id_map if new
    if rule.sutra_id not in new_state.rule_id_map_inv:
        idx = len(new_state.rule_id_map)
        new_state.rule_id_map[idx] = rule.sutra_id
        new_state.rule_id_map_inv[rule.sutra_id] = idx

    if new_state.visibility_matrix is None:
        new_state.visibility_matrix = PersistentVisibilityMatrix()

    # Apply mutation
    site_id = "site_0"
    for t in new_state.tokens:
        curr_state = t.graph.get(t.current_state_id)
        if curr_state.phoneme in rule.conditioning_factors or rule.effect_type in ("BHAVATI_TRANSFORM",):
            new_token_state = TokenState(
                state_id=f"{curr_state.state_id}_{rule.sutra_id}_{rule.effect_type}",
                phoneme=rule.effect_type if rule.effect_type != "BHAVATI_TRANSFORM" else "bhavati",
                lexical_category=curr_state.lexical_category,
                rule_id_applied=rule.sutra_id,
                parent_ids=frozenset([curr_state.state_id])
            )
            t.graph.register(new_token_state)
            t.current_state_id = new_token_state.state_id
            site_id = curr_state.state_id
            break

    new_state.applied_rules.append((rule.sutra_id, site_id))
    new_state.trace.append(f"Applied rule {rule.sutra_id} producing {rule.effect_type}")
    return new_state


def run_derivation(
    initial_state: DerivationState,
    rules:         List[RuleObject],
    config:        TraditionConfig,
    evaluator:     SemanticConditionEvaluator,
    resolver:      ConflictResolver
) -> List[DerivationState]:
    """
    Returns all terminal derivation states (one per valid derivational path).
    Uses a work queue to manage branches; preserves non-fatal ambiguity forks cleanly.
    """
    work_queue: deque = deque([initial_state])
    terminal: List[DerivationState] = []

    while work_queue:
        state = work_queue.popleft()

        candidates = [
            r for r in rules
            if is_eligible(r, state, evaluator, config) and r.sutra_id not in [app[0] for app in state.applied_rules]
        ]

        if not candidates:
            terminal.append(state)
            continue

        try:
            result = resolver.resolve(candidates, state)
        except AmbiguousDerivationError:
            # Demote to non-fatal branch preservation
            result = ResolutionResult(is_branch=True, is_unresolved=True, alternatives=candidates)

        if result.is_unresolved:
            for alt in result.alternatives:
                forked_state = apply_rule(state.fork(), alt)
                forked_state.trace.append(
                    f"AMBIGUOUS_FORK: Unresolved priority between {[c.sutra_id for c in candidates]}"
                )
                work_queue.append(forked_state)
            continue
        elif result.is_branch:
            for alt in result.alternatives:
                new_state = apply_rule(state, alt)
                work_queue.append(new_state)
        elif result.chosen:
            new_state = apply_rule(state, result.chosen)
            work_queue.append(new_state)
        else:
            terminal.append(state)

    return terminal
