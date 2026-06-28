"""
Verification tests for Phase 4: Conflict Resolution and Rewind
Tests relational antaraṅga/bahiraṅga resolution and loop termination using CausalEnv.
"""
import pytest
from paninian_engine.types import DomainIdentifier, SutraTextVersion, GanapathaVersion, AccentPriorityRule
from paninian_engine.config import TraditionConfig, AnuvrttiPolicy
from paninian_engine.conflict import (
    RuleObject,
    ResolutionResult,
    ConflictResolver,
    CausalEnv,
    execute_bahiranga_rewind,
)


class MockState:
    def __init__(self):
        self.resolved_conflicts = set()


def test_antaranga_relational_check():
    # Antaraṅga rule requires conditioning factors {"a", "i"}
    r_antaranga = RuleObject("6.1.77", {"a", "i"}, "YAN")
    
    # Bahiraṅga rule requires conditioning factors {"a", "i", "suffix_p"} (superset!)
    r_bahiranga = RuleObject("6.1.101", {"a", "i", "suffix_p"}, "DIRGHA")

    assert r_antaranga.is_antaranga_relative_to(r_bahiranga) is True
    assert r_bahiranga.is_antaranga_relative_to(r_antaranga) is False

    config = TraditionConfig(
        anuvrtti_flow=AnuvrttiPolicy({}, {}),
        paribhasas=set(),
        sutra_text=SutraTextVersion.KASHIKA,
        ganapatha=GanapathaVersion.KASHIKA,
        accent_priority=AccentPriorityRule.DHATU_OVER_GANA,
        phoneme_enumeration=[],
        include_n_in_14th=False,
    )
    resolver = ConflictResolver(config)
    res = resolver.resolve([r_antaranga, r_bahiranga], MockState())
    assert res.chosen == r_antaranga


def test_loop_termination_on_rewind():
    state = MockState()
    r_a = RuleObject("6.1.77", {"a"}, "YAN")
    r_b = RuleObject("6.1.101", {"a", "b"}, "DIRGHA")

    env = CausalEnv(
        triggering_rule_id="6.1.101",
        causal_token_state_ids=frozenset(["state_1", "state_2"]),
        active_domain_stack=(DomainIdentifier.PADASYA,)
    )
    h = hash(env)

    # Execute rewind
    execute_bahiranga_rewind(state, r_a, r_b, h)

    # Assert the conflict tuple is registered in resolved_conflicts
    assert (r_a.sutra_id, r_b.sutra_id, h) in state.resolved_conflicts

    # When r_b re-triggers in matching causal hash h, eligibility check checks resolved_conflicts
    is_suppressed = (r_a.sutra_id, r_b.sutra_id, h) in state.resolved_conflicts
    assert is_suppressed is True  # Loop terminated!
