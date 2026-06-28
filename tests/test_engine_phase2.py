"""
Verification tests for Phase 2: Token Graph
Simulates a multi-step substitution chain and verifies causal ancestry isolation.
"""
import pytest
from paninian_engine.types import LexicalCategory
from paninian_engine.visibility import CausalVisibilityMatrix
from paninian_engine.graph import (
    TokenState,
    DerivationGraph,
    MorphoPhonemicToken,
    compute_samjna,
)


def test_multistep_substitution_and_sthanivadbhava():
    graph = DerivationGraph()

    # Initial state A (e.g. vowel 'i')
    state_a = TokenState(
        state_id="state_a",
        phoneme="i",
        lexical_category=LexicalCategory.ROOT,
        rule_id_applied=None,
        parent_ids=frozenset()
    )
    graph.register(state_a)

    # Substitution rule 6.1.77 (ik yan aci) replaces 'i' with 'y' -> State B
    state_b = TokenState(
        state_id="state_b",
        phoneme="y",
        lexical_category=LexicalCategory.ADESA,
        rule_id_applied="6.1.77",
        parent_ids=frozenset(["state_a"])
    )
    graph.register(state_b)

    # Another substitution or modification -> State C
    state_c = TokenState(
        state_id="state_c",
        phoneme="y_modified",
        lexical_category=LexicalCategory.ADESA,
        rule_id_applied="8.2.100",
        parent_ids=frozenset(["state_b"])
    )
    graph.register(state_c)

    token = MorphoPhonemicToken("state_c", graph)

    # Test get_substituend_for 6.1.77 -> should return State A!
    substituend = token.get_substituend_for("6.1.77")
    assert substituend is not None
    assert substituend.state_id == "state_a"
    assert substituend.phoneme == "i"


def test_simultaneous_branch_isolation():
    graph = DerivationGraph()

    # Initial root state
    root = TokenState("root", "a", LexicalCategory.ROOT, None, frozenset())
    graph.register(root)

    # Branch 1 produces state_b1 via rule R1
    b1 = TokenState("b1", "a1", LexicalCategory.ROOT, "R1", frozenset(["root"]))
    graph.register(b1)

    # Branch 2 produces state_b2 via rule R2 (simultaneous alternative)
    b2 = TokenState("b2", "a2", LexicalCategory.ROOT, "R2", frozenset(["root"]))
    graph.register(b2)

    # Token currently on Branch 1
    token_b1 = MorphoPhonemicToken("b1", graph)

    # Verify ancestors_of(b1) does NOT contain b2
    ancestors = graph.ancestors_of("b1")
    assert "root" in ancestors
    assert "b2" not in ancestors

    # Verify get_state_when looking for R2 returns empty on token_b1
    states_r2 = token_b1.get_state_when(lambda s: s.rule_id_applied == "R2")
    assert len(states_r2) == 0


def test_compute_samjna_with_visibility():
    graph = DerivationGraph()
    state_init = TokenState("init", "root_ph", LexicalCategory.ROOT, None, frozenset())
    graph.register(state_init)

    # Rule R1 turns root into something else (e.g. ADESA)
    state_mod = TokenState("mod", "mod_ph", LexicalCategory.ADESA, "R1", frozenset(["init"]))
    graph.register(state_mod)

    token = MorphoPhonemicToken("mod", graph)

    # Causal visibility matrix for 1 rule applied (index 0 corresponds to R1)
    matrix = CausalVisibilityMatrix()
    rule_id_map = {0: "R1"}

    # Case 1: Rule R1 is visible
    mask_visible = matrix.visibility_mask_for(0, 1, rule_id_map)
    assert compute_samjna(token, "adesa", mask_visible, graph) is True
    assert compute_samjna(token, "dhatu", mask_visible, graph) is False

    # Case 2: Rule R1 is causally suspended (asiddha) -> mask out R1
    matrix_suspended = matrix.mask(0, 0)
    mask_invisible = matrix_suspended.visibility_mask_for(0, 1, rule_id_map)
    # Under invisible mask, compute_samjna falls back to visible ancestor ('init') which is ROOT (dhatu)
    assert compute_samjna(token, "dhatu", mask_invisible, graph) is True
    assert compute_samjna(token, "adesa", mask_invisible, graph) is False
