import pytest
from paninian_engine.phonology import PhonologyBridge
from paninian_engine.pre_grammatical import PratyaharaEngine
from paninian_engine.config import TraditionConfig, AnuvrttiPolicy
from paninian_engine.types import AccentPriorityRule, SutraTextVersion, GanapathaVersion
from paninian_engine.conflict import RuleObject


@pytest.fixture
def pratyahara_engine():
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
    return PratyaharaEngine(config)


def test_pratyahara_queries(pratyahara_engine):
    bridge = PhonologyBridge(pratyahara_engine)
    
    # Check vowels against 'aC'
    assert bridge._is_in_pratyahara('a', 'aC')
    assert bridge._is_in_pratyahara('i', 'aC')
    assert bridge._is_in_pratyahara('e', 'aC')
    assert not bridge._is_in_pratyahara('k', 'aC')

    # Check consonants against 'haL'
    assert bridge._is_in_pratyahara('k', 'haL')
    assert bridge._is_in_pratyahara('t', 'haL')
    assert not bridge._is_in_pratyahara('a', 'haL')


def test_yan_sandhi(pratyahara_engine):
    bridge = PhonologyBridge(pratyahara_engine)
    rule = RuleObject(
        sutra_id="6.1.77",
        conditioning_factors=set(),
        effect_type="yan",
        left_context={"pratyahara": "iK"},
        right_context={"pratyahara": "aC"},
        operation={"op_type": "yan"}
    )

    # i + a -> y + a (stem ends with y)
    res, mutated = bridge.execute_pairwise_sandhi("dadhi", "atra", rule)
    assert mutated
    assert res == "dadhyatra"


def test_savarna_dirgha(pratyahara_engine):
    bridge = PhonologyBridge(pratyahara_engine)
    rule = RuleObject(
        sutra_id="6.1.101",
        conditioning_factors=set(),
        effect_type="dirgha",
        left_context={"pratyahara": "aK"},
        right_context={"pratyahara": "aK"},
        operation={"op_type": "savarna_dirgha"}
    )

    res, mutated = bridge.execute_pairwise_sandhi("rāma", "avatāra", rule)
    assert mutated
    assert res == "rāmāvatāra"


def test_guna_sandhi(pratyahara_engine):
    bridge = PhonologyBridge(pratyahara_engine)
    rule = RuleObject(
        sutra_id="6.1.87",
        conditioning_factors=set(),
        effect_type="guna",
        left_context={"exact_text": ["a", "ā"]},
        right_context={"pratyahara": "iK"},
        operation={"op_type": "guna"}
    )

    res, mutated = bridge.execute_pairwise_sandhi("rāma", "īśaḥ", rule)
    assert mutated
    assert res == "rāmeśaḥ"


def test_jhal_jaso_consonant_voicing(pratyahara_engine):
    bridge = PhonologyBridge(pratyahara_engine)
    rule = RuleObject(
        sutra_id="8.2.39",
        conditioning_factors=set(),
        effect_type="jas",
        left_context={"pratyahara": "jhaL"},
        operation={"op_type": "jhalam_jaso"}
    )

    res, mutated = bridge.execute_pairwise_sandhi("jagat", "nātha", rule)
    assert mutated
    assert res == "jagadnātha"
