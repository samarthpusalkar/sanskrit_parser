"""
Verification tests for Phase 3: Vivakṣā and Semantic Bridge
Tests separation of morphological exponent classes from semantic predicates, and Kāraka quantifier evaluation.
"""
import pytest
from paninian_engine.types import DomainType, ComparisonOp, LogicalOp, Quantifier
from paninian_engine.vivaksa import (
    LiteralNode,
    VariableNode,
    ComparisonNode,
    LogicalOpNode,
    QuantifierNode,
    LogicalPredicate,
    VivaksaAST,
    SemanticConditionEvaluator,
)


class MockDerivationContext:
    def __init__(self, semantic_state, domains):
        self.semantic_state = semantic_state
        self._domains = domains

    def domain_for(self, domain_type: DomainType):
        return self._domains.get(domain_type, [])


def test_lat_semantic_separation():
    # Speaker's intent: express present indicative temporal meaning
    # Notice that Laṭ is NOT anywhere in the Vivakṣā semantic state or predicate!
    vivaksa = VivaksaAST(root=LiteralNode("present_indicative", DomainType.TEMPORAL))
    
    context = MockDerivationContext(
        semantic_state={"temporal": "present_indicative"},
        domains={}
    )

    # Rule 3.2.123 trigger condition checks if temporal intent equals 'present_indicative'
    cond_3_2_123 = LogicalPredicate(
        root=ComparisonNode(
            left=VariableNode("temporal", DomainType.TEMPORAL),
            op=ComparisonOp.EQUALS,
            right=LiteralNode("present_indicative", DomainType.TEMPORAL)
        )
    )

    evaluator = SemanticConditionEvaluator()
    # The grammar independently confirms the semantic condition holds, allowing Laṭ affixation
    assert evaluator.eval_condition(vivaksa, cond_3_2_123, context) is True

    # If semantic intent is past tense (laṅ / liṭ), 3.2.123 condition fails
    context_past = MockDerivationContext(
        semantic_state={"temporal": "past"},
        domains={}
    )
    assert evaluator.eval_condition(vivaksa, cond_3_2_123, context_past) is False


def test_karaka_quantifier_condition():
    # Test a Kāraka quantifier condition for case suffix rule (e.g. 2.3.2 karmaṇi dvitīyā)
    # Checks EXISTS v in KARMAN domain such that v == 'devadatta'
    vivaksa = VivaksaAST(root=LiteralNode("express_karman", DomainType.VALENCE))

    context = MockDerivationContext(
        semantic_state={},
        domains={
            DomainType.KARMAN: ["rice", "devadatta"]
        }
    )

    cond_karman = LogicalPredicate(
        root=QuantifierNode(
            quantifier=Quantifier.EXISTS,
            variable=VariableNode("target_obj", DomainType.KARMAN),
            body=ComparisonNode(
                left=VariableNode("target_obj", DomainType.KARMAN),
                op=ComparisonOp.EQUALS,
                right=LiteralNode("rice", DomainType.KARMAN)
            )
        )
    )

    evaluator = SemanticConditionEvaluator()
    assert evaluator.eval_condition(vivaksa, cond_karman, context) is True

    # If looking for an object not in the KARMAN domain, should evaluate False
    cond_missing = LogicalPredicate(
        root=QuantifierNode(
            quantifier=Quantifier.EXISTS,
            variable=VariableNode("target_obj", DomainType.KARMAN),
            body=ComparisonNode(
                left=VariableNode("target_obj", DomainType.KARMAN),
                op=ComparisonOp.EQUALS,
                right=LiteralNode("chariot", DomainType.KARMAN)
            )
        )
    )
    assert evaluator.eval_condition(vivaksa, cond_missing, context) is False
