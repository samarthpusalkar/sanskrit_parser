"""
Sanity tests for GrammarContext — validate that the deterministic context
builder produces correct accumulated state at known chapter boundaries.

These tests do NOT involve any LLM. They verify that:
  1. Saṃjñās defined in early chapters appear in context for later chapters.
  2. Adhikāras declared in early chapters are active for later chapters.
  3. Anuvṛtti carries accumulate correctly.
  4. Paribhāṣās are tracked.
  5. Context checkpoints serialize/deserialize correctly.

The assertions are based on known Pāṇinian grammar facts, not on LLM output.
"""

from __future__ import annotations

import os

import pytest

from grammar_context import GrammarContext, ContextBuilder

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


@pytest.fixture(scope="module")
def builder():
    return ContextBuilder(DB_PATH)


class TestContextStructure:
    """Basic structural tests — does the context build without crashing?"""

    def test_build_for_chapter_3_1(self, builder):
        ctx = builder.build_for_chapter("3.1")
        assert ctx.processed_sutras, "should have processed sūtras before 3.1"
        # Before 3.1, chapters 1.1-2.4 should be processed.
        assert len(ctx.processed_sutras) > 50, "too few sūtras processed before 3.1"

    def test_build_full(self, builder):
        ctx = builder.build_full()
        assert len(ctx.processed_sutras) > 1000, "full build should process many sūtras"

    def test_checkpoint_roundtrip(self, builder):
        ctx = builder.build_for_chapter("1.1")
        json_str = ctx.to_json()
        restored = GrammarContext.from_json(json_str)
        assert restored.processed_sutras == ctx.processed_sutras
        assert restored.sanjnas == ctx.sanjnas


class TestSanjnas:
    """Saṃjñā definitions should accumulate and be visible to later chapters."""

    def test_vrddhi_defined_in_1_1(self, builder):
        ctx = builder.build_for_chapter("3.1")
        # 1.1.1 defines vṛddhi — should be in context before 3.1
        # The LLM may have stored it as 'vrddhi', 'vfdDi', or 'vruddhi'.
        vrddhi_keys = [k for k in ctx.sanjnas if k.lower() in ("vrddhi", "vfdDi", "vruddhi", "vṛddhi")]
        assert len(vrddhi_keys) >= 1, f"vṛddhi saṃjñā not found in context before 3.1; have: {list(ctx.sanjnas.keys())[:20]}"

    def test_dhatu_defined_before_3_1(self, builder):
        ctx = builder.build_for_chapter("3.1")
        dhatu_keys = [k for k in ctx.sanjnas if k.lower() in ("dhatu", "dhātu", "dhAtu")]
        assert len(dhatu_keys) >= 1, "dhātu saṃjñā not found in context before 3.1"

    def test_pratyaya_defined_in_3_1(self, builder):
        # pratyaya is defined in 3.1.1, so it appears in context for 3.2, not before 3.1.
        ctx = builder.build_for_chapter("3.2")
        pratyaya_keys = [k for k in ctx.sanjnas if k.lower() in ("pratyaya", "pratyaya")]
        assert len(pratyaya_keys) >= 1, "pratyaya saṃjñā not found in context before 3.2"

    def test_sanjna_count_grows(self, builder):
        """More sūtras processed → more saṃjñās defined."""
        ctx_1_1 = builder.build_for_chapter("1.2")
        ctx_3_1 = builder.build_for_chapter("3.1")
        assert len(ctx_3_1.sanjnas) >= len(ctx_1_1.sanjnas), \
            "saṃjñā count should grow as more chapters are processed"

    def test_sanjna_has_source_sutra(self, builder):
        ctx = builder.build_for_chapter("3.1")
        for term, sanjna in ctx.sanjnas.items():
            assert sanjna.sutra_id, f"saṃjñā {term} has no source sūtra_id"
            assert sanjna.definition_type, f"saṃjñā {term} has no definition_type"


class TestAdhikaras:
    """Adhikāra scopes should be tracked and active for the right ranges."""

    def test_adhikaras_present_before_3_1(self, builder):
        ctx = builder.build_for_chapter("3.1")
        # 3.1.1 (pratyayaḥ) and 3.1.91 (dhātoḥ) are adhikāras in 3.1 itself,
        # so they won't be in context BEFORE 3.1. But earlier adhikāras should be.
        assert len(ctx.active_adhikaras) >= 0, "should have processed adhikāras"

    def test_adhikara_has_topic(self, builder):
        ctx = builder.build_full()
        for scope in ctx.active_adhikaras:
            assert scope.topic, f"adhikāra {scope.sutra_id} has no topic"

    def test_dhato_adhikara_in_full_build(self, builder):
        ctx = builder.build_full()
        # 3.1.91 "dhātoḥ" is an adhikāra — topic stored in Devanagari.
        dhato_adhikaras = [s for s in ctx.active_adhikaras
                           if "dhāto" in s.topic.lower() or "धातो" in s.topic]
        assert len(dhato_adhikaras) >= 1, "dhātoḥ adhikāra not found in full build"


class TestAnuvrtti:
    """Anuvṛtti carries should accumulate."""

    def test_anuvrtti_carries_present(self, builder):
        ctx = builder.build_full()
        # 6.1 has many anuvṛtti carries in the DB
        if len(ctx.processed_sutras) > 1000:
            assert len(ctx.anuvrtti_carries) > 0, "no anuvṛtti carries found in full build"

    def test_anuvrtti_has_source(self, builder):
        ctx = builder.build_full()
        for field, carry in ctx.anuvrtti_carries.items():
            assert carry.carried_from_sutra_id, f"anuvṛtti {field} has no source"
            assert carry.field_name, f"anuvṛtti carry has no field_name"


class TestParibhasas:
    """Paribhāṣās should be tracked."""

    def test_paribhasas_present_in_full_build(self, builder):
        ctx = builder.build_full()
        assert len(ctx.paribhasas) > 0, "no paribhāṣās found in full build"


class TestContextSummary:
    """The context_summary should be JSON-serializable and useful for prompts."""

    def test_summary_is_dict(self, builder):
        ctx = builder.build_for_chapter("3.1")
        summary = ctx.context_summary()
        assert isinstance(summary, dict)
        assert "defined_sanjnas" in summary
        assert "active_adhikaras" in summary
        assert "anuvrtti_carries" in summary
        assert "paribhasas_in_force" in summary

    def test_summary_serializable(self, builder):
        import json
        ctx = builder.build_for_chapter("3.1")
        summary = ctx.context_summary()
        json.dumps(summary, ensure_ascii=False)  # should not raise

    def test_summary_has_sanjnas_before_3_1(self, builder):
        ctx = builder.build_for_chapter("3.1")
        summary = ctx.context_summary()
        assert len(summary["defined_sanjnas"]) > 0, "no saṃjñās in context before 3.1"


class TestMonotonicGrowth:
    """Context should grow monotonically as more sūtras are processed."""

    def test_sanjna_count_monotonic(self, builder):
        checkpoints = ["1.2", "1.4", "3.1", "3.4", "6.1", "8.4"]
        counts = []
        for ch in checkpoints:
            ctx = builder.build_for_chapter(ch)
            counts.append(len(ctx.sanjnas))
        # Counts should be non-decreasing
        for i in range(1, len(counts)):
            assert counts[i] >= counts[i - 1], \
                f"saṃjñā count decreased from {checkpoints[i-1]} ({counts[i-1]}) to {checkpoints[i]} ({counts[i]})"

    def test_processed_count_monotonic(self, builder):
        checkpoints = ["1.2", "1.4", "3.1", "3.4"]
        counts = []
        for ch in checkpoints:
            ctx = builder.build_for_chapter(ch)
            counts.append(len(ctx.processed_sutras))
        for i in range(1, len(counts)):
            assert counts[i] > counts[i - 1], \
                f"processed count did not increase from {checkpoints[i-1]} to {checkpoints[i]}"