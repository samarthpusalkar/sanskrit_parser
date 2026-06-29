"""
DSL Unit Tests — tests/test_dsl_unit.py

GATE tests that verify compiled sūtras actually match and produce correct output.
These tests FAIL if the DSL compiler produces sutras that can't execute correctly.
No "currently_fails" assertions — tests must pass by being correct, not by documenting bugs.
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
    """6.1.77: iko yan aci (iK → yaN before aC)"""

    def test_compiles_as_executable(self, compiler):
        s = compiler.compile_sutra("6.1.77")
        assert s.spec.is_executable
        assert s.spec.operation.compute_fn == "bijection"

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


class TestSutra6187:
    """6.1.87: ād guṇaḥ (a/ā + iK → guṇa)"""

    def test_compiles_as_executable(self, compiler):
        s = compiler.compile_sutra("6.1.87")
        assert s.spec.is_executable

    def test_matches_rAma_ISa(self, compiler):
        s = compiler.compile_sutra("6.1.87")
        assert s.matches("rAma", "ISa"), "6.1.87 should match rAma+ISa after corrections"

    def test_produces_rAmeSa(self, compiler):
        s = compiler.compile_sutra("6.1.87")
        new_left, new_right = s.apply("rAma", "ISa")
        assert new_left == "rAme", f"Expected 'rAme', got '{new_left}'"


class TestSutra6188:
    """6.1.88: vṛddhir eci (a/ā + eC → vṛddhi)"""

    def test_compiles_as_executable(self, compiler):
        s = compiler.compile_sutra("6.1.88")
        assert s.spec.is_executable

    def test_matches_tava_eva(self, compiler):
        s = compiler.compile_sutra("6.1.88")
        assert s.matches("tava", "eva"), "6.1.88 should match tava+eva after corrections"

    def test_produces_tavEva(self, compiler):
        s = compiler.compile_sutra("6.1.88")
        new_left, new_right = s.apply("tava", "eva")
        assert new_left == "tavE", f"Expected 'tavE', got '{new_left}'"


class TestSutra6101:
    """6.1.101: akaḥ savarṇe dīrghaḥ (aK + savarṇa → dīrgha)"""

    def test_compiles_as_executable(self, compiler):
        s = compiler.compile_sutra("6.1.101")
        assert s.spec.is_executable

    def test_matches_rAma_atra(self, compiler):
        s = compiler.compile_sutra("6.1.101")
        assert s.matches("rAma", "atra"), "6.1.101 should match rAma+atra after corrections"

    def test_produces_rAmAtra(self, compiler):
        s = compiler.compile_sutra("6.1.101")
        new_left, new_right = s.apply("rAma", "atra")
        assert new_left == "rAmA", f"Expected 'rAmA', got '{new_left}'"


class TestSutra8266:
    """8.2.66: saṣajuṣo ruḥ (s/ḥ → r before voiced)"""

    def test_compiles_as_executable(self, compiler):
        s = compiler.compile_sutra("8.2.66")
        assert s.spec.is_executable

    def test_matches_hariH_gacCati(self, compiler):
        s = compiler.compile_sutra("8.2.66")
        assert s.matches("hariH", "gacCati"), "8.2.66 should match hariH+gacCati"

    def test_produces_harir_gacCati(self, compiler):
        s = compiler.compile_sutra("8.2.66")
        new_left, new_right = s.apply("hariH", "gacCati")
        assert new_left == "harir", f"Expected 'harir', got '{new_left}'"


class TestSutra8323:
    """8.3.23: mo anusvāraḥ (m → ṃ before consonant)"""

    def test_compiles_as_executable(self, compiler):
        s = compiler.compile_sutra("8.3.23")
        assert s.spec.is_executable

    def test_matches_karam_vande(self, compiler):
        s = compiler.compile_sutra("8.3.23")
        assert s.matches("karam", "vande"), "8.3.23 should match karam+vande"

    def test_produces_karaM_vande(self, compiler):
        s = compiler.compile_sutra("8.3.23")
        new_left, new_right = s.apply("karam", "vande")
        assert new_left == "karaM", f"Expected 'karaM', got '{new_left}'"


class TestPratyaharaMatching:
    """Verify pratyahara matching works correctly"""

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
        result = executor.execute_sandhi("hari", "atra")
        assert result["joined"] == "haryatra", f"Expected 'haryatra', got '{result['joined']}'"
        assert "6.1.77" in result["applied_rule_ids"]

    def test_rAma_ISa_produces_rAmeSa(self, executor):
        result = executor.execute_sandhi("rAma", "ISa")
        assert result["joined"] == "rAmeSa", f"Expected 'rAmeSa', got '{result['joined']}'"
        assert "6.1.87" in result["applied_rule_ids"]

    def test_tava_eva_produces_tavEva(self, executor):
        result = executor.execute_sandhi("tava", "eva")
        assert result["joined"] == "tavEva", f"Expected 'tavEva', got '{result['joined']}'"
        assert "6.1.88" in result["applied_rule_ids"]

    def test_rAma_atra_produces_rAmAtra(self, executor):
        result = executor.execute_sandhi("rAma", "atra")
        assert result["joined"] == "rAmAtra", f"Expected 'rAmAtra', got '{result['joined']}'"
        assert "6.1.101" in result["applied_rule_ids"]