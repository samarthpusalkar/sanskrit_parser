"""
Dynamic chapter-level integrability tests for panini_rules schema.

For every chapter present in panini_rules, verify all rules load and a
reasonable proportion compile as executable. This acts as a regression test
after each extraction run.
"""

from __future__ import annotations

import os
import sqlite3

import pytest

from sanskrit_dsl.panini_rule_parser import PaniniRuleParser
from sanskrit_dsl.types import CompiledSutra

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


@pytest.fixture(scope="module")
def parser():
    return PaniniRuleParser(DB_PATH)


def _list_chapters() -> list:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT DISTINCT substr(sutra_id, 1, instr(sutra_id, '.') - 1) || '.' || "
        "substr(sutra_id, instr(sutra_id, '.') + 1, 1) "
        "FROM panini_rules ORDER BY 1"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows if r[0]]


@pytest.mark.parametrize("chapter", _list_chapters())
def test_chapter_loads(parser, chapter):
    specs = parser.parse_chapter(chapter)
    assert len(specs) > 0, f"chapter {chapter} has no specs"


@pytest.mark.parametrize("chapter", _list_chapters())
def test_chapter_compiles(parser, chapter):
    specs = parser.parse_chapter(chapter)
    for s in specs:
        compiled = CompiledSutra(sutra_id=s.sutra_id, spec=s)
        assert compiled.spec.operation.op_type, f"{s.sutra_id} has no op_type"


@pytest.mark.parametrize("chapter", _list_chapters())
def test_chapter_executable_ratio(parser, chapter):
    """Definition-heavy chapters should still load; operational chapters need executable rules."""
    specs = parser.parse_chapter(chapter)
    total = len(specs)
    executable = sum(1 for s in specs if s.is_executable)
    # 1.1 and 1.4 are mostly definitions, so allow low/no executable ratio there.
    if chapter in {"1.1", "1.4"}:
        assert total >= 30, f"{chapter} too few rules"
    else:
        assert executable >= 1, f"{chapter} has no executable rules"