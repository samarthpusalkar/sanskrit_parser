"""
Bootstrap data-backed rule_configs from the current AST compiler.

This migrates mechanically compiled RuleSpec objects into SQLite rows so runtime
execution can fetch rule semantics as data rather than relying on Python
sutra-id dispatch. It intentionally preserves the compiler's current output
instead of inventing per-sutra behavior here.
"""

import argparse
import sqlite3
from typing import Optional

from compiler.pipeline import MasterCompilerPipeline


def encode_condition(cond) -> str:
    if cond is None:
        return ""
    if cond.pratyahara:
        return f"PRAT:{cond.pratyahara}"
    return cond.exact_text or ""


def ensure_extended_schema(cur: sqlite3.Cursor) -> None:
    columns = {row[1] for row in cur.execute("PRAGMA table_info(rule_configs)").fetchall()}
    for col, ddl in {
        "target_context": "ALTER TABLE rule_configs ADD COLUMN target_context TEXT",
        "domain": "ALTER TABLE rule_configs ADD COLUMN domain TEXT",
        "source": "ALTER TABLE rule_configs ADD COLUMN source TEXT",
    }.items():
        if col not in columns:
            cur.execute(ddl)


def bootstrap_rule_configs(db_path: str, limit: Optional[int] = None, include_unresolved: bool = True) -> int:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        ensure_extended_schema(cur)
        cur.execute("DELETE FROM rule_configs WHERE source = 'bootstrap_ast'")
        cur.execute("DELETE FROM rule_configs WHERE source = 'unresolved'")
        conn.commit()

    MasterCompilerPipeline._compiled_cache = []
    MasterCompilerPipeline._loaded = False
    rules = MasterCompilerPipeline.compile_all(db_path)

    rows = []
    seen = set()
    for rule in rules:
        spec = rule.spec
        if spec.governance.get("source"):
            continue
        key = (spec.id, spec.name, spec.operation.op_type, spec.operation.substitute)
        if key in seen:
            continue
        seen.add(key)
        rows.append((
            spec.id,
            spec.name,
            encode_condition(spec.target_context),
            encode_condition(spec.left_context),
            encode_condition(spec.right_context),
            spec.operation.op_type,
            spec.operation.substitute,
            spec.governance.get("domain", "sapada"),
            "bootstrap_ast",
        ))
        if limit is not None and len(rows) >= limit:
            break

    if not rows:
        return 0

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        ensure_extended_schema(cur)
        cur.execute("DELETE FROM rule_configs WHERE source = 'bootstrap_ast'")
        cur.execute("DELETE FROM rule_configs WHERE source = 'unresolved'")
        cur.executemany(
            """
            INSERT INTO rule_configs
                (sutra_id, name, target_context, left_context, right_context,
                 operation, replacement, domain, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        if include_unresolved:
            cur.execute(
                """
                INSERT INTO rule_configs
                    (sutra_id, name, operation, replacement, domain, source)
                SELECT s.id, s.sutra_slp1, 'non_operational', '', 
                       CASE
                           WHEN CAST(substr(s.id, 1, instr(s.id, '.') - 1) AS INTEGER) > 8
                                OR (
                                    CAST(substr(s.id, 1, instr(s.id, '.') - 1) AS INTEGER) = 8
                                    AND CAST(substr(
                                        s.id,
                                        instr(s.id, '.') + 1,
                                        instr(substr(s.id, instr(s.id, '.') + 1), '.') - 1
                                    ) AS INTEGER) >= 2
                                )
                           THEN 'tripadi'
                           ELSE 'sapada'
                       END,
                       'unresolved'
                FROM sutras s
                WHERE NOT EXISTS (
                    SELECT 1 FROM rule_configs rc WHERE rc.sutra_id = s.id
                )
                """
            )
        conn.commit()
        unresolved_count = cur.execute("SELECT COUNT(*) FROM rule_configs WHERE source = 'unresolved'").fetchone()[0]
    return len(rows) + unresolved_count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/sanskrit_master.db")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-unresolved", action="store_true")
    args = parser.parse_args()
    count = bootstrap_rule_configs(args.db, args.limit, include_unresolved=not args.no_unresolved)
    print(f"Inserted/updated {count} generated rule_configs.")


if __name__ == "__main__":
    main()
