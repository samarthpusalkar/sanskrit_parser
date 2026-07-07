"""
Post-extraction validation pipeline for panini_rules schema.

This script reads all rows in `panini_rules` + child tables and checks:
1. Schema validity (rule_type, operation_type, numeric fields).
2. Pratyāhāra resolution for every context.
3. Compilability into CompiledSutra via PaniniRuleParser.
4. Per-chapter executability ratio.
5. Hurdle summary from research/hurdles.

Usage:
    python3 tools/validate_panini_rules.py
    python3 tools/validate_panini_rules.py --report validation.json
"""

from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

sys = __import__("sys")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.shiva_sutras import PratyaharaResolver
from sanskrit_dsl.panini_rule_parser import PaniniRuleParser
from sanskrit_dsl.types import CompiledSutra

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
HURDLES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "research", "hurdles")

CANONICAL_RULE_TYPES = frozenset({
    "vidhi", "niyama", "paribhasa", "adhikara", "atidesa",
    "samjna_definition", "pratyaya_definition", "anuvrtti_carry",
    "nirukti", "vibhasha", "non_operational",
})
CANONICAL_OPERATION_TYPES = frozenset({
    "exact_substitute", "substitute", "merge", "elide", "augment",
    "prakritibhava", "bijection", "bijection_substitute", "yan",
    "dirgha", "savarna_long", "ekadesha_savarna_dirgha",
    "guna", "ekadesha_guna", "vrddhi", "ekadesha_vrddhi",
    "visarga_sandhi", "anusvara", "natva", "samprasarana",
    "pararupa", "purva_rupa", "lopa", "luk", "slu",
    "pratyaya_insert", "niyama_prohibit", "non_operational",
})


def _connect(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def validate_schema(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Check basic schema validity of panini_rules rows."""
    invalid = []
    cursor = conn.execute(
        "SELECT sutra_id, rule_type, operation_type, left_consume, right_consume, "
        "is_executable, is_meta_rule, is_definition FROM panini_rules"
    )
    for row in cursor.fetchall():
        sid, rule_type, op_type, left_consume, right_consume, is_exec, is_meta, is_def = row
        errors = []
        if not sid:
            errors.append("missing sutra_id")
        if rule_type not in CANONICAL_RULE_TYPES:
            errors.append(f"invalid rule_type: {rule_type}")
        if op_type not in CANONICAL_OPERATION_TYPES:
            errors.append(f"invalid operation_type: {op_type}")
        for name, val in (
            ("left_consume", left_consume),
            ("right_consume", right_consume),
            ("is_executable", is_exec),
            ("is_meta_rule", is_meta),
            ("is_definition", is_def),
        ):
            if not isinstance(val, int):
                errors.append(f"{name} is not int: {val!r}")
            elif name in ("left_consume", "right_consume") and val < 0:
                errors.append(f"{name} negative: {val}")
        if errors:
            invalid.append({"sutra_id": sid, "errors": errors})
    return invalid


def validate_pratyaharas(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Check every pratyahara value in contexts resolves."""
    unresolvable = []
    cursor = conn.execute(
        "SELECT rule_id, context_role, pratyahara FROM panini_rule_contexts "
        "WHERE pratyahara IS NOT NULL AND pratyahara != ''"
    )
    for row in cursor.fetchall():
        rule_id, role, prat = row
        try:
            PratyaharaResolver.resolve(prat)
        except Exception as e:
            unresolvable.append({
                "sutra_id": rule_id,
                "context_role": role,
                "pratyahara": prat,
                "error": str(e),
            })
    return unresolvable


def validate_compilability(db_path: str) -> List[Dict[str, Any]]:
    """Check every rule can be loaded by PaniniRuleParser and compiled."""
    parser = PaniniRuleParser(db_path)
    conn = _connect(db_path)
    rows = conn.execute("SELECT sutra_id FROM panini_rules ORDER BY sutra_id").fetchall()
    conn.close()
    uncompilable = []
    for (sid,) in rows:
        try:
            spec = parser.parse(sid)
            compiled = CompiledSutra(sutra_id=sid, spec=spec)
            assert compiled.spec.operation.op_type is not None
        except Exception as e:
            uncompilable.append({"sutra_id": sid, "error": str(e)})
    return uncompilable


def chapter_executability(db_path: str) -> Dict[str, Dict[str, Any]]:
    """For each chapter, report total vs executable rules."""
    parser = PaniniRuleParser(db_path)
    conn = _connect(db_path)
    rows = conn.execute(
        "SELECT DISTINCT substr(sutra_id, 1, instr(sutra_id, '.') - 1) || '.' || "
        "substr(sutra_id, instr(sutra_id, '.') + 1, 1) FROM panini_rules ORDER BY 1"
    ).fetchall()
    conn.close()
    per_chapter: Dict[str, Dict[str, Any]] = {}
    for (chapter,) in rows:
        specs = parser.parse_chapter(chapter)
        total = len(specs)
        executable = sum(1 for s in specs if s.is_executable)
        per_chapter[chapter] = {
            "total": total,
            "executable": executable,
            "executable_pct": round(100 * executable / total, 1) if total else 0.0,
        }
    return per_chapter


def summarize_hurdles(hurdles_dir: str) -> Dict[str, Any]:
    """Read research/hurdles and group by error type."""
    if not os.path.exists(hurdles_dir):
        return {"total": 0, "by_type": {}}
    total = 0
    by_type: Counter = Counter()
    by_sutra: Dict[str, List[str]] = defaultdict(list)
    for fname in os.listdir(hurdles_dir):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(hurdles_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        sid = data.get("sutra_id", fname[:-5].replace("_", "."))
        errors = data.get("errors", [])
        if not errors and "description" in data:
            errors = [data["description"]]
        for err in errors:
            total += 1
            # Bucket by first word/token for grouping.
            bucket = err.split(":")[0].strip() if ":" in err else err.split()[0] if err else "unknown"
            by_type[bucket] += 1
            by_sutra[sid].append(err)
    return {
        "total": total,
        "by_type": dict(by_type),
        "by_sutra": dict(by_sutra),
    }


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Validate panini_rules extraction")
    ap.add_argument("--db-path", default=DB_PATH)
    ap.add_argument("--report", default=None, help="Path to write JSON report")
    args = ap.parse_args(argv)

    conn = _connect(args.db_path)
    try:
        schema_invalid = validate_schema(conn)
        unresolvable_pratyaharas = validate_pratyaharas(conn)
    finally:
        conn.close()

    uncompilable = validate_compilability(args.db_path)
    per_chapter = chapter_executability(args.db_path)
    hurdles = summarize_hurdles(HURDLES_DIR)

    total_rules = sum(ch["total"] for ch in per_chapter.values())
    total_executable = sum(ch["executable"] for ch in per_chapter.values())

    report = {
        "total_rules": total_rules,
        "total_executable": total_executable,
        "executable_pct": round(100 * total_executable / total_rules, 1) if total_rules else 0.0,
        "schema_invalid_count": len(schema_invalid),
        "schema_invalid": schema_invalid[:50],
        "unresolvable_pratyahara_count": len(unresolvable_pratyaharas),
        "unresolvable_pratyaharas": unresolvable_pratyaharas[:50],
        "uncompilable_count": len(uncompilable),
        "uncompilable": uncompilable[:50],
        "per_chapter": per_chapter,
        "hurdles": hurdles,
    }

    print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nReport written to {args.report}")

    if schema_invalid or unresolvable_pratyaharas or uncompilable:
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
