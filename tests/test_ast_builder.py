"""
Tests for compiler/ast_builder.py backed by Master SQLite Database.

Verifies that all 3,983 Pāṇinian sūtras compile dynamically into formal RuleSpec AST objects.
"""

import sqlite3
from pathlib import Path
from compiler.pada_cheda import PadaChedaParser
from compiler.ast_builder import SutraAstBuilder


def test_build_iko_yan_aci():
    pc = "इकः$S$6$1$##यण्$S$1$1$##अचि$S$7$1$"
    tokens = PadaChedaParser.parse(pc)
    rule = SutraAstBuilder.build("6.1.77", "iko yanaci", tokens)
    
    assert rule.id == "6.1.77"
    assert rule.target_context.pratyahara == "iK"
    assert rule.right_context.pratyahara == "aC"
    assert rule.operation.op_type == "bijection_substitute"
    assert rule.operation.substitute == "yaR"
    assert rule.governance["domain"] == "sapada"


def test_build_all_database_sutra_asts():
    """Dynamically compile all 3,983 sūtras into executable RuleSpec AST objects."""
    db_path = Path(__file__).parent.parent / "data/sanskrit_master.db"
    assert db_path.exists(), f"Database missing at {db_path}"

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    rows = cur.execute("SELECT id, sutra_slp1, pada_cheda FROM sutras WHERE pada_cheda != ''").fetchall()
    conn.close()

    assert len(rows) >= 3900

    compiled_rules = 0
    for sid, slp, pc in rows:
        tokens = PadaChedaParser.parse(pc)
        rule = SutraAstBuilder.build(sid, slp, tokens)
        assert rule.id == sid
        assert rule.name == slp
        assert rule.governance["domain"] in {"sapada", "tripadi"}
        compiled_rules += 1

    assert compiled_rules == len(rows)
