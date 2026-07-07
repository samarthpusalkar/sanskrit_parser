"""
GrammarContext package — running state of Pāṇinian grammar compilation.

Public API:
    from grammar_context import GrammarContext, ContextBuilder

    builder = ContextBuilder()
    ctx = builder.build_for_chapter("3.1")  # context before chapter 3.1
    summary = ctx.context_summary()
"""

from .context import (
    GrammarContext,
    SanjnaDefinition,
    AdhikaraScope,
    AnuvrttiCarry,
    ParibhasaAxiom,
)
from .builder import ContextBuilder

__all__ = [
    "GrammarContext",
    "SanjnaDefinition",
    "AdhikaraScope",
    "AnuvrttiCarry",
    "ParibhasaAxiom",
    "ContextBuilder",
]