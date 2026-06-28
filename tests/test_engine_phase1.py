"""
Verification tests for Phase 1: Foundations
Tests pratyāhāra expansion, Dhātupāṭha lookup for div-class roots, and Gaṇapāṭha membership.
"""
import pytest
from paninian_engine.types import (
    SemanticRole,
    SutraTextVersion,
    GanapathaVersion,
    AccentPriorityRule,
    AccentFeature,
)
from paninian_engine.config import (
    AnuvrttiPolicy,
    TraditionConfig,
)
from paninian_engine.pre_grammatical import (
    PratyaharaEngine,
    DhatupathaRecord,
    DhatupathaEngine,
    GanaMembershipRecord,
    GanapathaEngine,
)


def get_standard_mahesvara_sutras():
    return [
        ["a", "i", "u", "ṇ"],
        ["ṛ", "ḷ", "k"],
        ["e", "o", "ṅ"],
        ["ai", "au", "c"],
        ["h", "y", "v", "r", "ṭ"],
        ["l", "ṇ"],
        ["ñ", "m", "ṅ", "ṇ", "n", "m"], # Simplified 7th for testing
        ["jh", "bh", "ñ"],
        ["gh", "ḍh", "dh", "ṣ"],
        ["j", "b", "g", "ḍ", "d", "ś"],
        ["kh", "ph", "ch", "ṭh", "th", "c", "ṭ", "t", "v"],
        ["k", "p", "y"],
        ["ś", "ṣ", "s", "r"],
        ["h", "l"]
    ]


def test_pratyahara_expansion():
    config = TraditionConfig(
        anuvrtti_flow=AnuvrttiPolicy({}, {}),
        paribhasas=set(),
        sutra_text=SutraTextVersion.KASHIKA,
        ganapatha=GanapathaVersion.KASHIKA,
        accent_priority=AccentPriorityRule.DHATU_OVER_GANA,
        phoneme_enumeration=get_standard_mahesvara_sutras(),
        include_n_in_14th=False,
    )
    engine = PratyaharaEngine(config)

    # Test 'ac' -> all vowels: a, i, u, ṛ, ḷ, e, o, ai, au
    ac = engine.expand("ac")
    assert "a" in ac and "i" in ac and "au" in ac
    assert "k" not in ac
    assert "ṇ" not in ac # IT marker should not be included

    # Test 'ik' -> i, u, ṛ, ḷ
    ik = engine.expand("ik")
    assert "i" in ik and "u" in ik and "ṛ" in ik and "ḷ" in ik
    assert "a" not in ik


def test_dhatupatha_div_class():
    div_record = DhatupathaRecord(
        root_form="div",
        inherent_anubandhas={"u"}, # e.g. divu
        class_name="divadi",
        inherent_accent=AccentFeature.ANUDATTA
    )
    dp = DhatupathaEngine([div_record])
    config = TraditionConfig(
        anuvrtti_flow=AnuvrttiPolicy({}, {}),
        paribhasas=set(),
        sutra_text=SutraTextVersion.KASHIKA,
        ganapatha=GanapathaVersion.KASHIKA,
        accent_priority=AccentPriorityRule.DHATU_OVER_GANA,
        phoneme_enumeration=[],
        include_n_in_14th=False,
    )
    res = dp.lookup("div", config)
    assert res is not None
    assert res.class_name == "divadi"
    assert res.inherent_accent == AccentFeature.ANUDATTA


class MockToken:
    def __init__(self, root_id: str):
        self.root_id = root_id
        self.current_state_id = root_id


def test_ganapatha_membership():
    # Test contested or feature-rich gana membership across traditions
    rec_kashika = GanaMembershipRecord(
        root_id="gam",
        gana_name="bhvadi",
        anubandhas={"ḷ"},
        lexical_accent=AccentFeature.UDATTA
    )
    gp = GanapathaEngine([rec_kashika])
    token = MockToken("gam")
    config = TraditionConfig(
        anuvrtti_flow=AnuvrttiPolicy({}, {}),
        paribhasas=set(),
        sutra_text=SutraTextVersion.KASHIKA,
        ganapatha=GanapathaVersion.KASHIKA,
        accent_priority=AccentPriorityRule.DHATU_OVER_GANA,
        phoneme_enumeration=[],
        include_n_in_14th=False,
    )
    res = gp.lookup(token, "bhvadi", config)
    assert res is not None
    assert "ḷ" in res.anubandhas
