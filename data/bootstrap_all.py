"""
Bootstrap all derived lexicon tables in sanskrit_master.db.

Run after db_compiler.py or whenever sutras/rule data changes.
"""

import sqlite3
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data.bootstrap_sanjnas import build_sanjnas_table, populate_operational_terms, DB_PATH
from data.bootstrap_pratyahara_lexicon import build_pratyahara_lexicon


def bootstrap_all(db_path: str = DB_PATH, include_curated_rules: bool = True) -> None:
    conn = sqlite3.connect(db_path)
    build_sanjnas_table(conn)
    populate_operational_terms(conn)
    sanjnas_count = conn.execute("SELECT COUNT(*) FROM sanjnas").fetchone()[0]
    build_pratyahara_lexicon(conn)
    prat_count = conn.execute("SELECT COUNT(*) FROM pratyahara_lexicon").fetchone()[0]
    conn.close()
    print(f"\nBootstrap complete: sanjnas={sanjnas_count}, pratyahara_lexicon={prat_count}")

    if include_curated_rules:
        from data.enrich_curated_rules import enrich_curated_rules
        enrich_curated_rules(db_path)


if __name__ == "__main__":
    bootstrap_all()
