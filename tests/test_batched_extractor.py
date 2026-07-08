"""
Sanity tests for the batched contextual extractor.

Verifies prompt building and context accumulation without making LLM calls.
"""

from __future__ import annotations

import os

import pytest

from grammar_context import ContextBuilder
from grammar_context.batched_extractor import (
    build_batched_contextual_prompt,
    BatchedContextualExtractor,
)
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


class TestBatchedPromptBuilding:
    """Verify the batched context-aware prompt is well-formed."""

    def test_prompt_builds_for_batch(self, builder, schema, db):
        ctx = builder.build_up_to("3.1.68")
        sutras = db.load_sutras_for_chapter("3.1")[:5]
        prompt = build_batched_contextual_prompt(sutras, ctx, schema)
        assert isinstance(prompt, str)
        assert len(prompt) > 200

    def test_prompt_contains_all_sutras(self, builder, schema, db):
        ctx = builder.build_up_to("3.1.68")
        sutras = db.load_sutras_for_chapter("3.1")[:5]
        prompt = build_batched_contextual_prompt(sutras, ctx, schema)
        for s in sutras:
            assert s["id"] in prompt, f"{s['id']} not in prompt"

    def test_prompt_contains_batch_count(self, builder, schema, db):
        ctx = builder.build_up_to("3.1.68")
        sutras = db.load_sutras_for_chapter("3.1")[:5]
        prompt = build_batched_contextual_prompt(sutras, ctx, schema)
        assert "5" in prompt  # batch of 5
        assert "Sūtra 1/5" in prompt or "Sūtra 1" in prompt

    def test_prompt_contains_context(self, builder, schema, db):
        ctx = builder.build_up_to("3.1.68")
        sutras = db.load_sutras_for_chapter("3.1")[:5]
        prompt = build_batched_contextual_prompt(sutras, ctx, schema)
        assert "SAṆJÑĀS" in prompt
        assert "vrddhi" in prompt or "vṛddhi" in prompt

    def test_prompt_contains_sequential_instruction(self, builder, schema, db):
        ctx = builder.build_up_to("3.1.68")
        sutras = db.load_sutras_for_chapter("3.1")[:5]
        prompt = build_batched_contextual_prompt(sutras, ctx, schema)
        assert "IN ORDER" in prompt or "in order" in prompt
        assert "JSON ARRAY" in prompt or "JSON array" in prompt
        assert "track" in prompt.lower()

    def test_prompt_contains_schema(self, builder, schema, db):
        ctx = builder.build_up_to("3.1.68")
        sutras = db.load_sutras_for_chapter("3.1")[:5]
        prompt = build_batched_contextual_prompt(sutras, ctx, schema)
        assert "rule_type" in prompt
        assert "operation_type" in prompt


class TestBatchedExtractorInit:
    """The extractor should initialize and handle edge cases."""

    def test_init(self):
        ext = BatchedContextualExtractor(model="test", batch_size=5)
        assert ext.model == "test"
        assert ext.batch_size == 5

    def test_extract_empty_chapter(self):
        ext = BatchedContextualExtractor(model="test", batch_size=5)
        stats = ext.extract_chapter("99.99")
        assert stats["total"] == 0
        assert stats["attempted"] == 0