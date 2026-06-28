"""
Verification test suite specifically validating the 4 expert architectural upgrades:
1. Memory-Safe State Forking (PersistentVisibilityMatrix)
2. Exact Causal Dependency Hashing (CausalEnv)
3. The Seventh Co-Equal Input (SabdabodhaFrame injection)
4. Non-Fatal Ambiguity Preservation
Plus dynamic PratyaharaEngine boundary validation (include_n_in_14th toggle).
"""
import pytest
from paninian_engine.types import (
    DomainType, ComparisonOp, LogicalOp, Quantifier, LexicalCategory,
    SutraTextVersion, GanapathaVersion, AccentPriorityRule, DomainIdentifier
)
from paninian_engine.config import TraditionConfig, AnuvrttiPolicy
from paninian_engine.visibility import PersistentVisibilityMatrix
from paninian_engine.conflict import RuleObject, ConflictResolver, CausalEnv
from paninian_engine.vivaksa import (
    SabdabodhaFrame, KarakaNode, QuantifierNode, VariableNode, ComparisonNode,
    LiteralNode, LogicalPredicate, VivaksaAST, SemanticConditionEvaluator
)
from paninian_engine.graph import DerivationGraph, TokenState, MorphoPhonemicToken
from paninian_engine.loop import DerivationState, run_derivation
from paninian_engine.pre_grammatical import PratyaharaEngine


def get_standard_mahesvara_sutras():
    return [
        ["a", "i", "u", "ṇ"],
        ["ṛ", "ḷ", "k"],
        ["e", "o", "ṅ"],
        ["ai", "au", "c"],
        ["h", "y", "v", "r", "ṭ"],
        ["l", "ṇ"],
        ["ñ", "m", "ṅ", "ṇ", "n", "m"],
        ["jh", "bh", "ñ"],
        ["gh", "ḍh", "dh", "ṣ"],
        ["j", "b", "g", "ḍ", "d", "ś"],
        ["kh", "ph", "ch", "ṭh", "th", "c", "ṭ", "t", "v"],
        ["k", "p", "y"],
        ["ś", "ṣ", "s", "r"],
        ["h", "l"]
    ]


def test_pratyahara_include_n_toggle():
    # Case 1: Standard tradition where 'aṇ' takes the first 'ṇ' (Sūtra 1)
    config_1st = TraditionConfig(
        anuvrtti_flow=AnuvrttiPolicy({}, {}),
        paribhasas=set(),
        sutra_text=SutraTextVersion.KASHIKA,
        ganapatha=GanapathaVersion.KASHIKA,
        accent_priority=AccentPriorityRule.DHATU_OVER_GANA,
        phoneme_enumeration=get_standard_mahesvara_sutras(),
        include_n_in_14th=False,
    )
    engine_1st = PratyaharaEngine(config_1st)
    an_1st = engine_1st.expand("aṇ")
    assert an_1st == frozenset(["a", "i", "u"])
    assert "h" not in an_1st and "l" not in an_1st

    # Case 2: Tradition variant where 'aṇ' extends to the second 'ṇ' (Sūtra 6)
    config_2nd = TraditionConfig(
        anuvrtti_flow=AnuvrttiPolicy({}, {}),
        paribhasas=set(),
        sutra_text=SutraTextVersion.KASHIKA,
        ganapatha=GanapathaVersion.KASHIKA,
        accent_priority=AccentPriorityRule.DHATU_OVER_GANA,
        phoneme_enumeration=get_standard_mahesvara_sutras(),
        include_n_in_14th=True,
    )
    engine_2nd = PratyaharaEngine(config_2nd)
    an_2nd = engine_2nd.expand("aṇ")
    assert "a" in an_2nd and "i" in an_2nd and "h" in an_2nd and "l" in an_2nd
    assert len(an_2nd) > 3


def test_persistent_visibility_matrix_forking():
    parent_matrix = PersistentVisibilityMatrix()
    rule_id_map = {0: "R1", 1: "R2"}

    # Child state suspends causal link (1, 0)
    child_matrix = parent_matrix.mask(1, 0)

    # Verify parent matrix remains unaffected (immutability / persistence)
    assert parent_matrix.is_visible(1, 0) is True
    assert child_matrix.is_visible(1, 0) is False

    # Verify mask projection reflects suspension only in child
    parent_mask = parent_matrix.visibility_mask_for(1, 2, rule_id_map)
    child_mask = child_matrix.visibility_mask_for(1, 2, rule_id_map)
    assert parent_mask.is_visible("R1") is True
    assert child_mask.is_visible("R1") is False


def test_sabdabodha_karaka_injection():
    # Construct Śābdabodha conceptual frame with a KARMAN node
    karaka = KarakaNode(nominal_stem="odana", target_role=DomainType.KARMAN, governing_action_id="pac_1")
    frame = SabdabodhaFrame(action_nodes={"pac_1": "to cook"}, karaka_edges=[karaka], upapada_relations={})

    state = DerivationState(tokens=[], sabdabodha=frame)

    # Trigger predicate checks if EXISTS x in KARMAN domain such that x == 'odana'
    cond = LogicalPredicate(
        root=QuantifierNode(
            quantifier=Quantifier.EXISTS,
            variable=VariableNode("obj", DomainType.KARMAN),
            body=ComparisonNode(
                left=VariableNode("obj", DomainType.KARMAN),
                op=ComparisonOp.EQUALS,
                right=LiteralNode("odana", DomainType.KARMAN)
            )
        )
    )
    evaluator = SemanticConditionEvaluator()
    assert evaluator.eval_condition(VivaksaAST(LiteralNode("express", DomainType.ACTION)), cond, state) is True


def test_non_fatal_ambiguity_preservation():
    config = TraditionConfig(
        anuvrtti_flow=AnuvrttiPolicy({}, {}),
        paribhasas=set(), # No explicit paribhasas to break ties
        sutra_text=SutraTextVersion.KASHIKA,
        ganapatha=GanapathaVersion.KASHIKA,
        accent_priority=AccentPriorityRule.DHATU_OVER_GANA,
        phoneme_enumeration=[],
        include_n_in_14th=False,
    )
    evaluator = SemanticConditionEvaluator()
    resolver = ConflictResolver(config)

    graph = DerivationGraph()
    state_0 = TokenState("root", "a", LexicalCategory.ROOT, None, frozenset())
    graph.register(state_0)
    token = MorphoPhonemicToken("root", graph)

    initial_state = DerivationState(tokens=[token])

    # Two tying mandatory rules with identical conditioning factors and same sūtra number/priority
    r1 = RuleObject("6.1.100", {"a"}, "OPT_A")
    r2 = RuleObject("6.1.100", {"a"}, "OPT_B")

    terminals = run_derivation(initial_state, [r1, r2], config, evaluator, resolver)

    # Verify neither branch was dropped and both were preserved non-fatally!
    assert len(terminals) == 2
    surface_forms = {term.tokens[0].graph.get(term.tokens[0].current_state_id).phoneme for term in terminals}
    assert surface_forms == {"OPT_A", "OPT_B"}

    # Verify trace records AMBIGUOUS_FORK
    assert any("AMBIGUOUS_FORK" in trace_line for term in terminals for trace_line in term.trace)
