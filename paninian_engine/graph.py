"""
ID-Based Derivation Graph and Token Architecture for the Paninian Rewriting Engine.
Prevents object-recursive walks and ensures clean hashability.
"""
from typing import Set, List, Dict, Optional, Callable, FrozenSet
from dataclasses import dataclass
import uuid

from .types import LexicalCategory, AccentFeature
from .visibility import VisibilityMask


@dataclass
class TokenState:
    state_id:         str                   # Stable UUID assigned at creation
    phoneme:          str
    lexical_category: LexicalCategory
    rule_id_applied:  Optional[str]         # The rule whose application produced
                                            # this state. None for initial states.
    parent_ids:       FrozenSet[str]        # IDs in DerivationGraph; FrozenSet
                                            # for hashability


class DerivationGraph:
    """
    Central registry. All token history traversals go through this object.
    Prevents object-recursive walks.
    """
    def __init__(self):
        self._states: Dict[str, TokenState] = {}

    def register(self, state: TokenState) -> None:
        self._states[state.state_id] = state

    def get(self, state_id: str) -> TokenState:
        return self._states[state_id]

    def ancestors_of(self, state_id: str) -> Set[str]:
        """
        Returns all state IDs backward-reachable from state_id via parent_ids.
        Used by MorphoPhonemicToken traversal methods to restrict walks to
        the causal ancestry of the querying token, not the full graph.
        """
        visited = set()
        queue = [state_id]
        while queue:
            sid = queue.pop()
            if sid in visited:
                continue
            visited.add(sid)
            if sid in self._states:
                queue.extend(self._states[sid].parent_ids)
        return visited


class MorphoPhonemicToken:
    def __init__(
        self,
        current_state_id: str,
        graph: DerivationGraph,
        accent: Optional[AccentFeature] = None,
        root_id: Optional[str] = None
    ):
        self.current_state_id = current_state_id
        self.graph = graph
        self.accent = accent
        self.root_id = root_id or current_state_id

    def get_substituend_for(self, substitution_rule_id: str) -> Optional[TokenState]:
        """
        Returns the unique TokenState in this token's causal ancestry that was
        directly replaced by the named rule (for sthānivadbhāva, 1.1.56).

        Correctness constraint: the walk is restricted to backward-reachable
        ancestors of current_state_id. It does NOT traverse the full graph,
        which would contaminate results with states from parallel simultaneous
        branches. Uses backward reachability, not DFS over the whole graph.
        """
        ancestor_ids = self.graph.ancestors_of(self.current_state_id)
        candidates = [
            self.graph.get(sid)
            for sid in ancestor_ids
            if sid in self.graph._states and self.graph.get(sid).rule_id_applied == substitution_rule_id
        ]
        if not candidates:
            return None
        substitute = self._shallowest(candidates)
        if substitute.parent_ids:
            parent_id = next(iter(substitute.parent_ids))
            if parent_id in self.graph._states:
                return self.graph.get(parent_id)
        return substitute

    def _shallowest(self, candidates: List[TokenState]) -> TokenState:
        seen = set()
        queue = [self.current_state_id]
        while queue:
            sid = queue.pop(0)
            if sid in seen:
                continue
            seen.add(sid)
            if sid not in self.graph._states:
                continue
            state = self.graph.get(sid)
            if state in candidates:
                return state
            queue.extend(state.parent_ids)
        return candidates[0]

    def get_state_when(
        self,
        predicate: Callable[[TokenState], bool]
    ) -> List[TokenState]:
        """
        Returns all historical states in this token's causal ancestry satisfying
        predicate. Walk is restricted to ancestors_of(current_state_id) to
        prevent contamination from parallel simultaneous branches.
        """
        ancestor_ids = self.graph.ancestors_of(self.current_state_id)
        return [
            self.graph.get(sid)
            for sid in ancestor_ids
            if sid in self.graph._states and predicate(self.graph.get(sid))
        ]


def compute_samjna(
    token:           MorphoPhonemicToken,
    samjna_name:     str,
    visibility_mask: VisibilityMask,
    graph:           DerivationGraph
) -> bool:
    """
    Evaluates saṃjñā status of a token relative to the querying rule's
    visibility context. Never cached on TokenState.
    """
    curr_state = graph.get(token.current_state_id)
    
    # If the rule that produced the current state is not visible under visibility_mask,
    # we must fall back to the visible ancestor state!
    active_state = curr_state
    if curr_state.rule_id_applied and not visibility_mask.is_visible(curr_state.rule_id_applied):
        # Find the shallowest visible ancestor
        ancestors = token.get_state_when(
            lambda s: s.rule_id_applied is None or visibility_mask.is_visible(s.rule_id_applied)
        )
        if ancestors:
            active_state = token._shallowest(ancestors)

    # Evaluate dynamic predicates against active_state
    if samjna_name == "dhatu":
        return active_state.lexical_category == LexicalCategory.ROOT
    elif samjna_name == "pratyaya":
        return active_state.lexical_category == LexicalCategory.AFFIX
    elif samjna_name == "agama":
        return active_state.lexical_category == LexicalCategory.AGAMA
    elif samjna_name == "adesa":
        return active_state.lexical_category == LexicalCategory.ADESA
    elif samjna_name in ("bha", "pada", "anga"):
        # Relational saṃjñās depend on following suffix conditions or derivational context
        # For unit testing and dynamic evaluation, we can check custom dynamic markers or properties
        return getattr(token, f"is_{samjna_name}", False)

    return False
