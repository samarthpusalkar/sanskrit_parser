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


def bootstrap_rule_configs(db_path: str, limit: Optional[int] = None) -> int:
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
        columns = {row[1] for row in cur.execute("PRAGMA table_info(rule_configs)").fetchall()}
        for col, ddl in {
            "target_context": "ALTER TABLE rule_configs ADD COLUMN target_context TEXT",
            "domain": "ALTER TABLE rule_configs ADD COLUMN domain TEXT",
            "source": "ALTER TABLE rule_configs ADD COLUMN source TEXT",
        }.items():
            if col not in columns:
                cur.execute(ddl)
        cur.execute("DELETE FROM rule_configs WHERE source = 'bootstrap_ast'")
        cur.executemany(
            """
            INSERT INTO rule_configs
                (sutra_id, name, target_context, left_context, right_context,
                 operation, replacement, domain, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/sanskrit_master.db")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    count = bootstrap_rule_configs(args.db, args.limit)
    print(f"Inserted {count} bootstrapped rule_configs.")


if __name__ == "__main__":
    main()
