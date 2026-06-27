"""
Tests for compiler/pada_cheda.py backed by Master SQLite Database.

Verifies that analytical Vibhakti parsing executes cleanly across all 3,983 Pāṇinian Sūtras.
"""

import sqlite3
from pathlib import Path
from compiler.pada_cheda import PadaChedaParser


def test_parse_vidhi_basic():
    # ikah (Genitive) guna-vriddhi (Nominative)
    pc = "इकः$S$6$1$##गुण-वृद्धी$S$1$2$"
    tokens = PadaChedaParser.parse(pc)
    
    assert len(tokens) == 2
    assert tokens[0].slp1 == "ikaH"
    assert tokens[0].case == 6
    assert tokens[0].is_target is True
    
    assert tokens[1].slp1 == "guRa-vfdDI"
    assert tokens[1].case == 1
    assert tokens[1].is_substitute is True


def test_parse_all_database_sutras():
    """Verify open-vocabulary parsing across all 3,983 compiled sūtras in SQLite."""
    db_path = Path(__file__).parent.parent / "data/sanskrit_master.db"
    assert db_path.exists(), f"Database missing at {db_path}"

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    rows = cur.execute("SELECT id, sutra_slp1, pada_cheda FROM sutras WHERE pada_cheda != ''").fetchall()
    conn.close()

    assert len(rows) >= 3900, f"Expected >3900 sūtras, found {len(rows)}"

    valid_parses = 0
    for sid, slp, pc in rows:
        tokens = PadaChedaParser.parse(pc)
        assert isinstance(tokens, list)
        valid_parses += 1

    assert valid_parses == len(rows)
