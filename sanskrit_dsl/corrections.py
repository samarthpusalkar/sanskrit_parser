"""
Parser Corrections — DEPRECATED

This file contained hand-annotated corrections for 7 sutras where the old
SutraAstBuilder misassigned vibhakti roles. This was a hardcoded shortcut,
not a real solution. It has been removed.

The correct path forward is LLM-assisted extraction (tools/llm_sutra_extractor.py)
which uses commentary context to correctly interpret sūtra semantics.

This file is kept as a placeholder to avoid import errors. It does nothing.
"""

PARSER_CORRECTIONS = {}


def apply_corrections(sutra_id, spec):
    """Deprecated. No corrections are applied."""
    pass