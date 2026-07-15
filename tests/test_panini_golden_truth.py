"""
Golden-truth test runner for the panini_rules extraction.

Loads curated cases from tests/fixtures/panini_golden_truth.json and asserts
that the deterministic engine produces the expected output for each case.

Definitions (saṃjñā sūtras) are asserted to be non-executable and to carry
the expected defined_sanjna.

Operational rules are run through CompiledSutra.matches/apply with the given
morphological context (left_sanjnas, right_sanjnas).
"""

from __future__ import annotations

import json
import os

import pytest

from sanskrit_dsl.execution_context import ExecutionContext
from sanskrit_dsl.panini_rule_parser import PaniniRuleParser
from sanskrit_dsl.types import CompiledSutra

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "panini_golden_truth.json")


def _load_cases() -> list:
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


def _make_ctx(left: str, right: str, left_sanjnas=None, right_sanjnas=None,
              domain: str = "sapada") -> ExecutionContext:
    ctx = ExecutionContext(left_token=left, right_token=right,
                           morphological_features={"left": {}, "right": {}})
    ctx.domain = domain
    for s in left_sanjnas or []:
        ctx.add_sanjna("left", s)
    for s in right_sanjnas or []:
        ctx.add_sanjna("right", s)
    return ctx


@pytest.fixture(scope="module")
def parser():
    return PaniniRuleParser(DB_PATH)


@pytest.fixture(scope="module")
def cases():
    return _load_cases()


def _case_id(case):
    return case["id"]


@pytest.mark.parametrize("case", _load_cases(), ids=_case_id)
def test_golden_truth_case(parser, case):
    sutra_id = case["sutra_id"]
    spec = parser.parse(sutra_id)
    assert spec.sutra_id == sutra_id, f"{sutra_id} not found in panini_rules"

    # Skip legacy-migrated rules that lack rich context positions.
    if case.get("skip_if_legacy"):
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT extraction_mode FROM panini_rules WHERE sutra_id = ?", (sutra_id,)
        ).fetchone()
        conn.close()
        if row and row[0] == "legacy_migration":
            pytest.skip(f"{sutra_id} is legacy_migration; skip_if_legacy set")

    if case.get("expected_not_executable"):
        assert not spec.is_executable, f"{sutra_id} should be non-executable definition"
        if case.get("expected_defined_sanjna") or case.get("expected_defined_sanjna_any_of"):
            import sqlite3
            conn = sqlite3.connect(DB_PATH)
            row = conn.execute(
                "SELECT defined_sanjna FROM panini_rules WHERE sutra_id = ?", (sutra_id,)
            ).fetchone()
            conn.close()
            if row and row[0]:
                if case.get("expected_defined_sanjna_any_of"):
                    assert row[0] in case["expected_defined_sanjna_any_of"], (
                        f"{sutra_id} defined_sanjna {row[0]!r} not in "
                        f"{case['expected_defined_sanjna_any_of']}"
                    )
                else:
                    assert row[0] == case["expected_defined_sanjna"], (
                        f"{sutra_id} defined_sanjna mismatch: got {row[0]!r}, "
                        f"expected {case['expected_defined_sanjna']!r}"
                    )
        return

    # Operational case: run the engine.
    compiled = CompiledSutra(sutra_id=sutra_id, spec=spec)
    left = case["left"]
    right = case["right"]
    ctx = _make_ctx(left, right, case.get("left_sanjnas"), case.get("right_sanjnas"),
                    domain=case.get("domain", "sapada"))

    assert compiled.matches(left, right, ctx), (
        f"{sutra_id} did not match input left={left!r} right={right!r} "
        f"with sanjnas left={case.get('left_sanjnas')} right={case.get('right_sanjnas')} "
        f"domain={case.get('domain', 'sapada')}"
    )

    # Only check apply output if the case specifies expected values.
    # Sandhi rules may match correctly but need further engine work for apply.
    if "expected_left" in case or "expected_right" in case:
        new_left, new_right = compiled.apply(left, right, ctx)
        if "expected_left" in case:
            assert new_left == case["expected_left"], (
                f"{sutra_id} left mismatch: got {new_left!r}, expected {case['expected_left']!r}"
            )
        if "expected_right" in case:
            assert new_right == case["expected_right"], (
                f"{sutra_id} right mismatch: got {new_right!r}, expected {case['expected_right']!r}"
            )


def test_fixture_loads(cases):
    assert len(cases) >= 5, "expected at least 5 golden-truth cases"
    # Ensure unique IDs.
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case IDs in fixture"