"""
Sanity tests for the new panini_rules schema parser.

These verify that extracted rules can be loaded into SutraSpec objects and
that the runtime engine can match/apply at least the simplest 3.1 rules.
"""

from __future__ import annotations

import os
import sqlite3

import pytest

from sanskrit_dsl.panini_rule_parser import PaniniRuleParser
from sanskrit_dsl.types import SutraContext, SutraOperation, SutraSpec

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


@pytest.fixture
def parser():
    return PaniniRuleParser(DB_PATH)


class TestParserBasics:
    def test_parse_known_sutra(self, parser):
        spec = parser.parse("3.1.68")
        assert spec.sutra_id == "3.1.68"
        assert spec.rule_type == "vidhi"
        assert spec.operation.op_type == "pratyaya_insert"
        assert spec.operation.replacement == "Sap"

    def test_parse_missing_sutra(self, parser):
        spec = parser.parse("99.99.99")
        assert spec.parsed_by == "not_found"

    def test_contexts_loaded(self, parser):
        spec = parser.parse("3.1.68")
        assert spec.left_context is not None
        assert spec.right_context is not None
        assert "dhatu" in spec.left_context.sanjna_required
        assert "sArvadhAtuka" in spec.right_context.sanjna_required

    def test_sanjna_definition(self, parser):
        spec = parser.parse("3.1.32")
        assert spec.rule_type == "samjna_definition"
        assert spec.operation.op_type == "non_operational"

    def test_chapter_parse(self, parser):
        specs = parser.parse_chapter("3.1")
        assert len(specs) == 150
        ids = {s.sutra_id for s in specs}
        assert "3.1.1" in ids
        assert "3.1.150" in ids


class TestCodeCompatibility:
    def test_3_1_68_is_executable(self, parser):
        spec = parser.parse("3.1.68")
        assert spec.is_executable

    def test_3_1_32_is_not_executable(self, parser):
        spec = parser.parse("3.1.32")
        assert not spec.is_executable

    def test_operation_has_consume(self, parser):
        spec = parser.parse("3.1.7")
        assert spec.operation.left_consume >= 0
        assert spec.operation.right_consume >= 0

    def test_compile_and_match_with_sanjna(self, parser):
        from sanskrit_dsl.types import CompiledSutra

        spec = parser.parse("3.1.68")
        compiled = CompiledSutra(sutra_id=spec.sutra_id, spec=spec)

        # Without dhatu/sarvadhatuka tags, should not match.
        assert not compiled.matches("bhU", "ti")

        # With tags, should match.
        ctx = _make_context("bhU", "ti", left_sanjnas={"dhatu"}, right_sanjnas={"sArvadhAtuka"})
        assert compiled.matches("bhU", "ti", ctx)

        left, right = compiled.apply("bhU", "ti", ctx)
        assert left == "bhU"
        assert right == "Sapti"  # emit_side right, emit=Sap inserted before ti


class TestCoverage:
    def test_3_1_complete_in_new_schema(self):
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM panini_rules WHERE sutra_id LIKE '3.1.%'").fetchone()[0]
        conn.close()
        assert count == 150

    def test_all_extracted_chapters_present(self, parser):
        chapters = parser.list_chapters()
        assert "1.1" in chapters
        assert "3.1" in chapters
        assert "6.1" in chapters
        assert "8.2" in chapters


def _make_context(left: str, right: str, left_sanjnas=None, right_sanjnas=None):
    from sanskrit_dsl.execution_context import ExecutionContext

    ctx = ExecutionContext(left_token=left, right_token=right)
    for s in left_sanjnas or set():
        ctx.add_sanjna("left", s)
    for s in right_sanjnas or set():
        ctx.add_sanjna("right", s)
    return ctx
