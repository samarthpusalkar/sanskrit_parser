import pytest
from paninian_engine.conflict import RuleObject, ConflictResolver
from paninian_engine.config import TraditionConfig, AnuvrttiPolicy, ParibhasaAxiom
from paninian_engine.types import AccentPriorityRule, SutraTextVersion, GanapathaVersion, AmbiguousDerivationError


@pytest.fixture
def dummy_config():
    return TraditionConfig(
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
            ['jh', 'bh', 'ñ']
        ],
        include_n_in_14th=False
    )


def test_conflict_resolver_sorting_with_paribhasa(dummy_config):
    # Add paribhāṣā 1.4.2 (vipratiṣedhe paraṃ kāryam)
    config_with_paribhasa = dummy_config
    config_with_paribhasa.paribhasas = {ParibhasaAxiom("1.4.2", "vipratiṣedhe paraṃ kāryam", "Astadhyayi")}
    resolver = ConflictResolver(config_with_paribhasa)

    r1 = RuleObject(sutra_id="6.1.77", conditioning_factors={"i"}, effect_type="y")
    r2 = RuleObject(sutra_id="6.1.101", conditioning_factors={"i"}, effect_type="I")

    # Para (later rule 6.1.101) wins over 6.1.77 when paribhāṣā is active
    res = resolver.resolve([r1, r2], state=None)
    assert res.chosen == r2
    assert res.chosen.sutra_id == "6.1.101"


def test_conflict_resolver_strict_ambiguity_without_paribhasa(dummy_config):
    # Without paribhāṣā, ties halt with AmbiguousDerivationError
    dummy_config.paribhasas = set()
    resolver = ConflictResolver(dummy_config)

    r1 = RuleObject(sutra_id="6.1.77", conditioning_factors={"i"}, effect_type="y")
    r2 = RuleObject(sutra_id="6.1.101", conditioning_factors={"i"}, effect_type="I")

    with pytest.raises(AmbiguousDerivationError):
        resolver.resolve([r1, r2], state=None)


def test_conflict_resolver_nitya(dummy_config):
    resolver = ConflictResolver(dummy_config)

    r1 = RuleObject(sutra_id="6.1.77", conditioning_factors={"i"}, effect_type="y", is_nitya=True)
    r2 = RuleObject(sutra_id="6.1.101", conditioning_factors={"i"}, effect_type="I", is_nitya=False)

    # Nitya rule wins even if earlier in sūtra order
    res = resolver.resolve([r1, r2], state=None)
    assert res.chosen == r1
    assert res.chosen.sutra_id == "6.1.77"


def test_conflict_resolver_antaranga(dummy_config):
    resolver = ConflictResolver(dummy_config)

    # r1 conditioning factors is a subset of r2
    r1 = RuleObject(sutra_id="1.1.1", conditioning_factors={"a"}, effect_type="x")
    r2 = RuleObject(sutra_id="1.1.2", conditioning_factors={"a", "b"}, effect_type="y")

    res = resolver.resolve([r1, r2], state=None)
    assert res.chosen == r1
