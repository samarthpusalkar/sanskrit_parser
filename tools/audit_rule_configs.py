"""
Audit rule_configs for semantic enrichment candidates.

The bootstrapper intentionally migrates current compiler output as data. This
auditor separates stable executable configs from rows that are probably only
syntactic placeholders and should be manually enriched with domain semantics.
"""

import argparse
import sqlite3
from collections import Counter


WEAK_OPERATIONS = {
    "exact_substitute",
    "governance",
    "sanjna_substitute",
}

SEMANTIC_OPERATIONS = {
    "merge",
    "substitute",
    "insert",
    "elide",
    "voice",
    "nasalize",
    "palatalize",
    "purva_rupa",
    "visarga_utva",
    "ro_ri_dirgha",
    "anusvara",
    "parasavarna",
    "natva",
    "right_substitute",
    "bijection_substitute",
    "dirgha",
    "prohibit",
}


def looks_glossy(value: str) -> bool:
    if not value:
        return False
    return "-" in value or len(value) > 8


def audit(db_path: str, limit: int) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT rc.*, s.sutra_slp1, s.pada_cheda
            FROM rule_configs rc
            LEFT JOIN sutras s ON s.id = rc.sutra_id
            ORDER BY rc.sutra_id, rc.id
            """
        ).fetchall()

    by_source = Counter(row["source"] or "unknown" for row in rows)
    by_op = Counter(row["operation"] or "" for row in rows)

    candidates = []
    for row in rows:
        reasons = []
        op = row["operation"] or ""
        replacement = row["replacement"] or ""
        target = row["target_context"] or row["left_context"] or ""
        right = row["right_context"] or ""
        if op in WEAK_OPERATIONS:
            reasons.append(f"weak-op:{op}")
        if op not in SEMANTIC_OPERATIONS:
            reasons.append(f"unknown-op:{op}")
        if looks_glossy(replacement):
            reasons.append("glossy-replacement")
        if looks_glossy(target):
            reasons.append("glossy-target")
        if looks_glossy(right):
            reasons.append("glossy-right-context")
        if not target and op not in {"governance"}:
            reasons.append("missing-target")
        if row["source"] == "bootstrap_ast" and reasons:
            candidates.append((row, reasons))

    print("Rule config coverage")
    print(f"  total rows: {len(rows)}")
    print(f"  by source: {dict(by_source)}")
    print(f"  top operations: {by_op.most_common(20)}")
    print()
    print(f"Semantic enrichment candidates: {len(candidates)}")
    for row, reasons in candidates[:limit]:
        print(
            f"{row['sutra_id']} | {row['sutra_slp1']} | op={row['operation']} "
            f"target={row['target_context'] or row['left_context'] or ''} "
            f"right={row['right_context'] or ''} replacement={row['replacement'] or ''} "
            f"| {', '.join(reasons)}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/sanskrit_master.db")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    audit(args.db, args.limit)


if __name__ == "__main__":
    main()
