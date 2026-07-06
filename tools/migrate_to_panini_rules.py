"""
Migration script — tools/migrate_to_panini_rules.py

Copies data from the old `rules` + `rule_*` hybrid tables into the clean
`panini_rules` + `panini_rule_*` tables. This is a one-time cleanup so that the
new extractor and parser have a single source of truth.

Run once after creating the new schema:
    python3 tools/create_panini_rules_schema.py
    python3 tools/migrate_to_panini_rules.py

If you already re-extracted chapter 3.1 into `panini_rules`, this migration
will skip those rows (INSERT OR IGNORE) so your fresh extraction is preserved.
"""

from __future__ import annotations

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")


def migrate(conn: sqlite3.Connection) -> dict:
    stats = {"rules_copied": 0, "contexts_copied": 0, "conditions_copied": 0,
             "axioms_copied": 0, "anuvrtti_links_copied": 0, "prerequisites_copied": 0}

    # Rules
    rows = conn.execute(
        "SELECT * FROM rules WHERE sutra_id NOT IN (SELECT sutra_id FROM panini_rules)"
    ).fetchall()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(rules)").fetchall()]
    col_str = ", ".join(cols)
    placeholders = ", ".join(["?"] * len(cols))
    insert_sql = f"INSERT OR IGNORE INTO panini_rules ({col_str}) VALUES ({placeholders})"
    for row in rows:
        conn.execute(insert_sql, row)
    stats["rules_copied"] = len(rows)

    # Contexts
    rows = conn.execute(
        "SELECT * FROM rule_contexts WHERE rule_id NOT IN (SELECT rule_id FROM panini_rule_contexts)"
    ).fetchall()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(rule_contexts)").fetchall()]
    col_str = ", ".join(cols)
    placeholders = ", ".join(["?"] * len(cols))
    insert_sql = f"INSERT OR IGNORE INTO panini_rule_contexts ({col_str}) VALUES ({placeholders})"
    for row in rows:
        conn.execute(insert_sql, row)
    stats["contexts_copied"] = len(rows)

    # Conditions
    rows = conn.execute(
        "SELECT * FROM rule_conditions WHERE rule_id NOT IN (SELECT rule_id FROM panini_rule_conditions)"
    ).fetchall()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(rule_conditions)").fetchall()]
    col_str = ", ".join(cols)
    placeholders = ", ".join(["?"] * len(cols))
    insert_sql = f"INSERT OR IGNORE INTO panini_rule_conditions ({col_str}) VALUES ({placeholders})"
    for row in rows:
        conn.execute(insert_sql, row)
    stats["conditions_copied"] = len(rows)

    # Axioms
    rows = conn.execute(
        "SELECT * FROM rule_paribhasa_axioms WHERE rule_id NOT IN (SELECT rule_id FROM panini_rule_paribhasa_axioms)"
    ).fetchall()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(rule_paribhasa_axioms)").fetchall()]
    col_str = ", ".join(cols)
    placeholders = ", ".join(["?"] * len(cols))
    insert_sql = f"INSERT OR IGNORE INTO panini_rule_paribhasa_axioms ({col_str}) VALUES ({placeholders})"
    for row in rows:
        conn.execute(insert_sql, row)
    stats["axioms_copied"] = len(rows)

    # Anuvrtti links
    rows = conn.execute(
        "SELECT * FROM rule_anuvrtti_links WHERE rule_id NOT IN (SELECT rule_id FROM panini_rule_anuvrtti_links)"
    ).fetchall()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(rule_anuvrtti_links)").fetchall()]
    col_str = ", ".join(cols)
    placeholders = ", ".join(["?"] * len(cols))
    insert_sql = f"INSERT OR IGNORE INTO panini_rule_anuvrtti_links ({col_str}) VALUES ({placeholders})"
    for row in rows:
        conn.execute(insert_sql, row)
    stats["anuvrtti_links_copied"] = len(rows)

    # Prerequisites
    rows = conn.execute(
        "SELECT * FROM chapter_prerequisites WHERE (chapter_prefix, prerequisite_sutra_id) NOT IN (SELECT chapter_prefix, prerequisite_sutra_id FROM panini_chapter_prerequisites)"
    ).fetchall()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(chapter_prerequisites)").fetchall()]
    col_str = ", ".join(cols)
    placeholders = ", ".join(["?"] * len(cols))
    insert_sql = f"INSERT OR IGNORE INTO panini_chapter_prerequisites ({col_str}) VALUES ({placeholders})"
    for row in rows:
        conn.execute(insert_sql, row)
    stats["prerequisites_copied"] = len(rows)

    conn.commit()
    return stats


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    stats = migrate(conn)
    conn.close()
    print("Migration complete:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
