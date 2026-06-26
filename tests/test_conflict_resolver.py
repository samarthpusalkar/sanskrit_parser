"""
Tests for Vyākaraṇa Jurisprudence Conflict Resolver.
"""

from rule_engine.conflict import RuleMatch, ConflictResolver
from rule_engine.dsl import RuleSpec, ConditionSpec
from vm.context import DerivationContext
from vm.token import DagToken


def test_antara_span_overrides_para():
    # Rule A: Wide span (bahiraṅga spanning tokens 0 to 3)
    rule_wide = RuleSpec("ext.1", "External Sandhi", "vidhi", 100, ConditionSpec())
    match_wide = RuleMatch(rule_wide, target_idx=0, right_idx=3)

    # Rule B: Narrow span (antaraṅga spanning tokens 1 to 2)
    rule_narrow = RuleSpec("int.1", "Internal Guna", "vidhi", 100, ConditionSpec())
    match_narrow = RuleMatch(rule_narrow, target_idx=1, right_idx=2)

    ctx = DerivationContext(tape=[DagToken("a") for _ in range(4)])
    winner = ConflictResolver.choose([match_wide, match_narrow], ctx)

    # Narrow span (span=1) must beat wide span (span=3)
    assert winner.rule.id == "int.1"
