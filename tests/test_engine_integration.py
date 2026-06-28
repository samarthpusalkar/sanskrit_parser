import pytest
from paninian_engine.loop import DerivationState, run_derivation, apply_rule, is_eligible
from paninian_engine.graph import MorphoPhonemicToken, TokenState, DerivationGraph
from paninian_engine.types import LexicalCategory, AccentPriorityRule, SutraTextVersion, GanapathaVersion
from paninian_engine.config import TraditionConfig, AnuvrttiPolicy
from paninian_engine.phonology import PhonologyBridge
from paninian_engine.pre_grammatical import PratyaharaEngine
from paninian_engine.conflict import RuleObject, ConflictResolver
from paninian_engine.vivaksa import SemanticConditionEvaluator


@pytest.fixture
def engine_components():
    config = TraditionConfig(
        anuvrtti_flow=AnuvrttiPolicy({}, {}),
        paribhasas=set(),
        sutra_text=SutraTextVersion.CRITICAL,
        ganapatha=GanapathaVersion.KASHIKA,
        accent_priority=AccentPriorityRule.DHATU_OVER_GANA,
        phoneme_enumeration=[
            ['a', 'i', 'u', 'ṇ'],
            ['ṛ', 'ḷ', 'k'],
            ['e', 'o', 'ṅ'],
            ['ai', 'au', 'c'],
            ['h', 'y', 'v', 'r', 'ṭ'],
            ['l', 'ṇ'],
            ['ñ', 'm', 'ṅ', 'ṇ', 'n', 'm'],
            ['jh', 'bh', 'ñ'],
            ['gh', 'ḍh', 'dh', 'ṣ'],
            ['j', 'b', 'g', 'ḍ', 'd', 'ś'],
            ['kh', 'ph', 'ch', 'ṭh', 'th', 'c', 'ṭ', 't', 'v'],
            ['k', 'p', 'y'],
            ['ś', 'ṣ', 's', 'r'],
            ['h', 'l']
        ],
        include_n_in_14th=False
    )
    pe = PratyaharaEngine(config)
    bridge = PhonologyBridge(pe)
    resolver = ConflictResolver(config)
    evaluator = SemanticConditionEvaluator()
    return config, bridge, resolver, evaluator


def create_token(phoneme: str, cat: LexicalCategory) -> MorphoPhonemicToken:
    g = DerivationGraph()
    s = TokenState(state_id="init", phoneme=phoneme, lexical_category=cat, rule_id_applied="none", parent_ids=frozenset())
    g.register(s)
    return MorphoPhonemicToken(graph=g, current_state_id="init")


def test_integration_guna_derivation(engine_components):
    config, bridge, resolver, evaluator = engine_components

    t1 = create_token("rāmā", LexicalCategory.ROOT)
    t2 = create_token("īśaḥ", LexicalCategory.AFFIX)

    state = DerivationState(tokens=[t1, t2], phonology_bridge=bridge)

    guna_rule = RuleObject(
        sutra_id="6.1.87",
        conditioning_factors=set(),
        effect_type="guna",
        left_context={"exact_text": ["a", "ā"]},
        right_context={"pratyahara": "iK"},
        operation={"op_type": "guna"}
    )

    assert is_eligible(guna_rule, state, evaluator, config)
    new_state = apply_rule(state, guna_rule)

    assert new_state.tokens[0].graph.get(new_state.tokens[0].current_state_id).phoneme == "rāmeśaḥ"
    assert new_state.tokens[1].graph.get(new_state.tokens[1].current_state_id).phoneme == ""


def test_integration_boundary_preservation(engine_components):
    config, bridge, resolver, evaluator = engine_components

    t1 = create_token("kām", LexicalCategory.ROOT)
    t2 = create_token("api", LexicalCategory.AFFIX)

    state = DerivationState(tokens=[t1, t2], phonology_bridge=bridge)

    # Rule 8.3.23 (mo'nusvāraḥ) only applies before haL (consonants).
    # Since 'api' starts with vowel 'a' (aC), 8.3.23 is NOT eligible.
    anusvara_rule = RuleObject(
        sutra_id="8.3.23",
        conditioning_factors=set(),
        effect_type="ṃ",
        left_context={"exact_text": "m"},
        right_context={"pratyahara": "haL"},
        operation={"op_type": "mo_anusvarah"}
    )

    assert not is_eligible(anusvara_rule, state, evaluator, config)

    # Words remain separated (kām + api -> kām api) without aggressive string gluing!
    assert state.tokens[0].graph.get(state.tokens[0].current_state_id).phoneme == "kām"
    assert state.tokens[1].graph.get(state.tokens[1].current_state_id).phoneme == "api"
