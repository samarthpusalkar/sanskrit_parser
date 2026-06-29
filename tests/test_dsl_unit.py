"""
DSL Unit Tests — tests/test_dsl_unit.py

GATE tests that verify compiled sūtras actually match and produce correct output.

HONEST STATE:
- 6.1.77 (iko yan aci) works end-to-end via the clean vibhakti parser
- 6.1.101 (akaḥ savarṇe dīrghaḥ) works end-to-end via LLM extraction
- 6.1.87 (ād guṇaḥ) and 6.1.88 (vṛddhir eci) await LLM extraction; the tests
  below document that no LLM row is present yet and will flip to positive
  assertions once extraction is run for them.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(".."))

from sanskrit_dsl.compiler import SutraCompiler
from sanskrit_dsl.executor import DSLExecutor


@pytest.fixture(scope="module")
def compiler():
    return SutraCompiler()


@pytest.fixture(scope="module")
def executor():
    return DSLExecutor()


class TestSutra6177:
    """6.1.77: iko yan aci (iK → yaN before aC) — WORKS via clean parser"""

    def test_compiles_as_executable(self, compiler):
        s = compiler.compile_sutra("6.1.77")
        assert s.spec.is_executable

    def test_matches_hari_atra(self, compiler):
        s = compiler.compile_sutra("6.1.77")
        assert s.matches("hari", "atra")

    def test_produces_correct_output(self, compiler):
        s = compiler.compile_sutra("6.1.77")
        new_left, new_right = s.apply("hari", "atra")
        assert new_left == "hary"
        assert new_right == "atra"

    def test_matches_guru_atra(self, compiler):
        s = compiler.compile_sutra("6.1.77")
        assert s.matches("guru", "atra")

    def test_produces_gurvatra(self, compiler):
        s = compiler.compile_sutra("6.1.77")
        new_left, new_right = s.apply("guru", "atra")
        assert new_left == "gurv"


class TestSutra6101:
    """6.1.101: akaḥ savarṇe dīrghaḥ — homogeneous vowel pair → dīrgha.

    Now works end-to-end via LLM extraction (target=aK pratyahara,
    right_context=savarṇa treated as the savarṇa meta-term wildcard).
    """

    def test_compiles_as_executable(self, compiler):
        s = compiler.compile_sutra("6.1.101")
        assert s.spec.is_executable
        assert s.spec.parsed_by == "llm_extract"

    def test_matches_rAma_atra(self, compiler):
        s = compiler.compile_sutra("6.1.101")
        assert s.matches("rAma", "atra")

    def test_produces_dirgha_merge(self, compiler):
        s = compiler.compile_sutra("6.1.101")
        new_left, new_right = s.apply("rAma", "atra")
        assert new_left == "rAmA"
        assert new_right == "tra"


class TestSutrasNeedingLLMExtraction:
    """
    6.1.87 (ād guṇaḥ) and 6.1.88 (vṛddhir eci) are not yet LLM-extracted.
    These tests document the honest current state: the clean parser cannot
    handle them, and no LLM row is present yet. Once extraction is run for
    these sūtras, replace these with positive output assertions.
    """

    def test_6187_not_yet_extracted(self, compiler):
        """6.1.87: ād guṇaḥ — awaits LLM extraction."""
        s = compiler.compile_sutra("6.1.87")
        assert s.spec.parsed_by != "llm_extract", \
            "6.1.87 now has an LLM row — flip this test to a positive assertion"

    def test_6188_not_yet_extracted(self, compiler):
        """6.1.88: vṛddhir eci — awaits LLM extraction."""
        s = compiler.compile_sutra("6.1.88")
        assert s.spec.parsed_by != "llm_extract", \
            "6.1.88 now has an LLM row — flip this test to a positive assertion"


class TestPratyaharaMatching:
    """Verify pratyahara matching works correctly (real, not return True)"""

    def test_iK_matches_i(self):
        from sanskrit_dsl.types import SutraContext, _context_matches
        ctx = SutraContext(pratyahara="iK", match_pos="end")
        assert _context_matches(ctx, "hari", "end")

    def test_iK_matches_u(self):
        from sanskrit_dsl.types import SutraContext, _context_matches
        ctx = SutraContext(pratyahara="iK", match_pos="end")
        assert _context_matches(ctx, "guru", "end")

    def test_iK_does_not_match_a(self):
        from sanskrit_dsl.types import SutraContext, _context_matches
        ctx = SutraContext(pratyahara="iK", match_pos="end")
        assert not _context_matches(ctx, "rAma", "end")

    def test_aC_matches_a(self):
        from sanskrit_dsl.types import SutraContext, _context_matches
        ctx = SutraContext(pratyahara="aC", match_pos="start")
        assert _context_matches(ctx, "atra", "start")

    def test_aC_does_not_match_k(self):
        from sanskrit_dsl.types import SutraContext, _context_matches
        ctx = SutraContext(pratyahara="aC", match_pos="start")
        assert not _context_matches(ctx, "kama", "start")


class TestDSLExecutor:
    """Test the full execution path through the DSL executor"""

    def test_hari_atra_produces_haryatra(self, executor):
        """6.1.77 works end-to-end through the executor"""
        result = executor.execute_sandhi("hari", "atra")
        assert result["joined"] == "haryatra", f"Expected 'haryatra', got '{result['joined']}'"
        assert "6.1.77" in result["applied_rule_ids"]