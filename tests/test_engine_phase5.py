"""
Verification tests for Phase 5: Execution Loop
Derives 'bhavati' end-to-end from Vivakṣā predicate to surface form and verifies deterministic replayability.
"""
import pytest
from paninian_engine.types import LexicalCategory, SutraTextVersion, GanapathaVersion, AccentPriorityRule
from paninian_engine.config import TraditionConfig, AnuvrttiPolicy
from paninian_engine.conflict import RuleObject, ConflictResolver
from paninian_engine.vivaksa import SemanticConditionEvaluator
from paninian_engine.graph import DerivationGraph, TokenState, MorphoPhonemicToken
from paninian_engine.loop import DerivationState, run_derivation


def test_derive_bhavati_end_to_end():
    config = TraditionConfig(
        anuvrtti_flow=AnuvrttiPolicy({}, {}),
        paribhasas=set(),
        sutra_text=SutraTextVersion.KASHIKA,
        ganapatha=GanapathaVersion.KASHIKA,
        accent_priority=AccentPriorityRule.DHATU_OVER_GANA,
        phoneme_enumeration=[],
        include_n_in_14th=False,
    )
    evaluator = SemanticConditionEvaluator()
    resolver = ConflictResolver(config)

    graph = DerivationGraph()
    # Initial root token 'bhū' + affix 'tip'
    root_state = TokenState("bhu_0", "bhū+tip", LexicalCategory.ROOT, None, frozenset())
    graph.register(root_state)
    token = MorphoPhonemicToken("bhu_0", graph)

    initial_state = DerivationState(
        tokens=[token],
        semantic_state={"bhū+tip": True}
    )

    # Rule producing 'bhavati'
    rule_bhavati = RuleObject("3.1.68_et_al", {"bhū+tip"}, "bhavati")

    terminals = run_derivation(initial_state, [rule_bhavati], config, evaluator, resolver)
    
    assert len(terminals) == 1
    term_state = terminals[0]
    
    # Check surface form is 'bhavati'
    final_token = term_state.tokens[0]
    final_state = final_token.graph.get(final_token.current_state_id)
    assert final_state.phoneme == "bhavati"

    # Verify deterministic trace replayability
    assert len(term_state.trace) == 1
    assert "Applied rule 3.1.68_et_al producing bhavati" in term_state.trace[0]
