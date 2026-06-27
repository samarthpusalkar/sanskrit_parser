"""
Tests for Sandhi forward joining and backward splitting.
Dynamically loads complex Pāṇinian edge cases from forward_parser_test.json.
"""

import os
import json
import pytest
from pathlib import Path

from morphology.sandhi import SandhiEngine
from morphology.api import SanskritCompiler

# Load the JSON test cases
TEST_FILE = Path(__file__).parent / "forward_parser_test.json"
try:
    with TEST_FILE.open("r", encoding="utf-8") as f:
        forward_tests = json.load(f)
except FileNotFoundError:
    forward_tests = []

def test_legacy_forward_sandhi():
    # Legacy hardcoded checks (SLP1 internal encoding)
    assert SandhiEngine.join("rAma", "ISa") == "rAmeSa"
    assert SandhiEngine.join("yadi", "api") == "yadyapi"
    assert SandhiEngine.join("mahA", "OzaDi") == "mahOzaDi"


def test_backward_sandhi_split():
    splits = SandhiEngine.split("rAmeSa")
    assert ("rAma", "ISa") in splits or ("rAmA", "ISa") in splits


def test_api_wrapper():
    joined = SanskritCompiler.join_words("rāma", "īśa", output_encoding="iast")
    assert joined == "rāmeśa"


@pytest.mark.parametrize("case", forward_tests, ids=[c.get("id", "test") for c in forward_tests])
def test_json_forward_sandhi(case):
    """
    Dynamically tests the engine against the JSON dataset to ensure it correctly 
    resolves Tripādī and action-at-a-distance Pāṇinian operations.
    """
    tokens = case["input_tokens"]
    expected = case["expected_string"]
    
    is_samasa = "samāsa" in case.get("rule_tags", [])
    
    # Process sequentially for multiple tokens
    actual = tokens[0]
    for nxt in tokens[1:]:
        actual = SanskritCompiler.join_words(actual, nxt, output_encoding="iast", is_samasa=is_samasa)
    
    assert actual == expected, (
        f"Failed {case['id']} ({case['difficulty']}): {case['description']}\n"
        f"Tokens: {tokens}\nExpected: {expected}\nGot: {actual}"
    )
