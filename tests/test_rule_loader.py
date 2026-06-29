"""Tests for paninian_engine.rule_loader — DB → RuleObject bridge."""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from paninian_engine.rule_loader import load_sandhi_rules, make_tradition_config
from paninian_engine.phonology import _lookup_pratyahara_canonical


DB_PATH = "data/sanskrit_master.db"


@pytest.fixture(scope="module", autouse=True)
def ensure_lexicons():
    if not os.path.exists(DB_PATH):
        pytest.skip("sanskrit_master.db not found")
    from data.bootstrap_all import bootstrap_all
    bootstrap_all(DB_PATH)


def test_load_sandhi_rules_non_empty():
    rules = load_sandhi_rules(DB_PATH)
    assert len(rules) > 0


def test_rule_6_1_77_has_vowel_right_context():
    rules = load_sandhi_rules(DB_PATH)
    yan_rules = [r for r in rules if r.sutra_id.startswith("6.1.77")]
    assert yan_rules, "Expected at least one 6.1.77 rule"
    r = yan_rules[0]
    rc = r.right_context
    assert rc.get("pratyahara") or rc.get("phonetic_class") == "vowel"


def test_rule_8_3_23_has_consonant_right_context():
    rules = load_sandhi_rules(DB_PATH)
    anusvara = [r for r in rules if r.sutra_id.startswith("8.3.23")]
    assert anusvara, "Expected at least one 8.3.23 rule"
    r = anusvara[0]
    rc = r.right_context
    assert rc.get("phonetic_class") == "consonant" or rc.get("pratyahara")


def test_make_tradition_config():
    cfg = make_tradition_config(DB_PATH)
    assert len(cfg.phoneme_enumeration) == 14


def test_pratyahara_lexicon_alias():
    canonical = _lookup_pratyahara_canonical("aC", DB_PATH)
    assert canonical == "ac"
