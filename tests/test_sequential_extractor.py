"""
Sanity tests for the sequential extractor's prompt building.

These tests verify that:
  1. The context-aware prompt builds without crashing.
  2. The prompt includes the grammar context (saṃjñās, adhikāras).
  3. The prompt includes the sūtra being extracted.
  4. The prompt includes the JSON schema.
  5. The prompt is well-formed for LLM consumption.

No LLM calls are made — only prompt construction is tested.
"""

from __future__ import annotations

import os

import pytest

from grammar_context import ContextBuilder
from grammar_context.sequential_extractor import build_contextual_prompt, SequentialExtractor
from batch_panini_extractor import build_extraction_schema, ExtractorDB

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


@pytest.fixture(scope="module")
def builder():
    return ContextBuilder(DB_PATH)


@pytest.fixture(scope="module")
def schema():
    return build_extraction_schema()


@pytest.fixture(scope="module")
def db():
    return ExtractorDB(DB_PATH)


class TestPromptBuilding:
    """Verify the context-aware prompt is well-formed."""

    def test_prompt_builds_for_3_1_68(self, builder, schema, db):
        ctx = builder.build_up_to("3.1.68")
        sutras = db.load_sutras_for_chapter("3.1")
        sutra = next(s for s in sutras if s["id"] == "3.1.68")
        prompt = build_contextual_prompt(sutra, ctx, schema)
        assert isinstance(prompt, str)
        assert len(prompt) > 100, "prompt too short"

    def test_prompt_contains_sutra_id(self, builder, schema, db):
        ctx = builder.build_up_to("3.1.68")
        sutras = db.load_sutras_for_chapter("3.1")
        sutra = next(s for s in sutras if s["id"] == "3.1.68")
        prompt = build_contextual_prompt(sutra, ctx, schema)
        assert "3.1.68" in prompt
        assert "कर्तरि" in prompt or "शप्" in prompt  # sutra text

    def test_prompt_contains_context(self, builder, schema, db):
        ctx = builder.build_up_to("3.1.68")
        sutras = db.load_sutras_for_chapter("3.1")
        sutra = next(s for s in sutras if s["id"] == "3.1.68")
        prompt = build_contextual_prompt(sutra, ctx, schema)
        # Context should include defined saṃjñās.
        assert "DEFINED SAṆJÑĀS" in prompt or "SAṆJÑĀS" in prompt
        # vrddhi is defined in 1.1.1, should be in context before 3.1.68.
        assert "vrddhi" in prompt or "vṛddhi" in prompt or "vfdDi" in prompt

    def test_prompt_contains_schema(self, builder, schema, db):
        ctx = builder.build_up_to("3.1.68")
        sutras = db.load_sutras_for_chapter("3.1")
        sutra = next(s for s in sutras if s["id"] == "3.1.68")
        prompt = build_contextual_prompt(sutra, ctx, schema)
        assert "rule_type" in prompt
        assert "operation_type" in prompt
        assert "contexts" in prompt

    def test_prompt_contains_instruction(self, builder, schema, db):
        ctx = builder.build_up_to("3.1.68")
        sutras = db.load_sutras_for_chapter("3.1")
        sutra = next(s for s in sutras if s["id"] == "3.1.68")
        prompt = build_contextual_prompt(sutra, ctx, schema)
        assert "Return ONLY the JSON object" in prompt
        assert "Pāṇinian" in prompt


class TestContextGrowthInPrompt:
    """Prompts for later sūtras should have richer context than earlier ones."""

    def test_later_sutra_has_more_context(self, builder, schema, db):
        sutras = db.load_sutras_for_chapter("3.1")
        early = next(s for s in sutras if s["id"] == "3.1.1")
        late = next(s for s in sutras if s["id"] == "3.1.150")

        ctx_early = builder.build_up_to("3.1.1")
        ctx_late = builder.build_up_to("3.1.150")

        prompt_early = build_contextual_prompt(early, ctx_early, schema)
        prompt_late = build_contextual_prompt(late, ctx_late, schema)

        # The late prompt should be at least as rich (more saṃjñās defined by then).
        assert len(ctx_late.sanjnas) >= len(ctx_early.sanjnas)


class TestSequentialExtractorInit:
    """The extractor should initialize without crashing."""

    def test_init(self):
        ext = SequentialExtractor(model="test-model", delay=0, resume=False)
        assert ext.model == "test-model"
        assert ext.schema is not None

    def test_extract_chapter_empty(self):
        ext = SequentialExtractor(model="test-model", delay=0, resume=False)
        # Use a non-existent chapter — should return empty stats, not crash.
        stats = ext.extract_chapter("99.99")
        assert stats["total"] == 0
        assert stats["attempted"] == 0