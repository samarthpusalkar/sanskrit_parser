#!/usr/bin/env python3
"""
Coverage Validator — tools/coverage_validator.py

Quantitatively measures how many rules in the DB are actively interpreted
(i.e., compiled to a non-trivial operation) vs. silently discarded as
'non_operational'.

This is the COMPLETION METRIC the architecture plan requires:
  - Target: < 5% non_operational in sandhi-domain chapters (6.1, 8.x)
  - Current: ~50%+ in those chapters before Phase 1-5 rewrites

Running this tells you *exactly* what fraction of Pāṇini's grammar
the engine currently processes, without requiring any test file.

Usage:
    python tools/coverage_validator.py
    python tools/coverage_validator.py --domain all       # all chapters
    python tools/coverage_validator.py --domain sandhi    # 6.1 + 8.x only
    python tools/coverage_validator.py --chapter 8.2      # single chapter
"""

import sqlite3
import os
import sys
import argparse
from typing import Dict, List, Tuple, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")

# Chapters that matter most for external sandhi correctness
SANDHI_CHAPTERS = {"6.1", "8.2", "8.3", "8.4"}

# Operations that mean the rule is truly active
ACTIVE_OPS = {
    "exact_substitute", "dirgha", "elide", "pararupa", "purva_rupa",
    "ekadesha_vriddhi", "ekadesha_savarna_dirgha", "ekadesha_guna",
    "prakritibhava", "bijection", "augment", "agama", "sanjna_substitute"
}

# Operations that mean the rule is currently ignored
PASSIVE_OPS = {
    "non_operational", "governance"
}


def get_chapter(sutra_id: str) -> str:
    """Return 'A.B' from 'A.B.C'."""
    parts = sutra_id.split(".")
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[1]}"
    return parts[0]


def load_coverage(conn: sqlite3.Connection, chapter_filter: Optional[str] = None) -> Dict[str, Dict]:
    """
    Load rule stats from DB.
    Returns: {chapter: {total, active, passive, op_counts: {op: count}}}
    """
    rows = conn.execute(
        "SELECT rc.sutra_id, rc.operation, s.sutra_type FROM rule_configs rc "
        "JOIN sutras s ON rc.sutra_id = s.id ORDER BY rc.sutra_id"
    ).fetchall()

    stats: Dict[str, Dict] = {}
    for sutra_id, op, sutra_type in rows:
        ch = get_chapter(sutra_id)
        if chapter_filter and ch != chapter_filter and not sutra_id.startswith(chapter_filter + "."):
            continue
        if ch not in stats:
            stats[ch] = {"total": 0, "active": 0, "passive": 0, "op_counts": {}}
        stats[ch]["total"] += 1
        stats[ch]["op_counts"][op] = stats[ch]["op_counts"].get(op, 0) + 1
        if op in ACTIVE_OPS:
            stats[ch]["active"] += 1
        elif op in PASSIVE_OPS:
            stats[ch]["passive"] += 1

    return stats


def compute_totals(stats: Dict[str, Dict]) -> Tuple[int, int, int]:
    total = sum(v["total"] for v in stats.values())
    active = sum(v["active"] for v in stats.values())
    passive = sum(v["passive"] for v in stats.values())
    return total, active, passive


def is_sandhi_chapter(ch: str) -> bool:
    return ch in SANDHI_CHAPTERS or ch.startswith("6.1") or ch.startswith("8.")


def report(stats: Dict[str, Dict], domain: str = "all"):
    """Print the coverage table."""
    header = f"\n{'Chapter':<10} {'Total':>6} {'Active':>8} {'Passive':>8} {'Coverage%':>10}  {'Status':>8}"
    print(header)
    print("-" * len(header))

    chapters = sorted(stats.keys(), key=lambda c: [int(x) for x in c.split(".")])
    for ch in chapters:
        v = stats[ch]
        if domain == "sandhi" and not is_sandhi_chapter(ch):
            continue
        pct = 100.0 * v["active"] / v["total"] if v["total"] else 0.0
        target_pct = 95.0 if is_sandhi_chapter(ch) else 50.0
        status = "✅" if pct >= target_pct else ("⚠️ " if pct >= 40.0 else "❌")
        print(f"  {ch:<8} {v['total']:>6} {v['active']:>8} {v['passive']:>8} {pct:>9.1f}%  {status}")

    total, active, passive = compute_totals(
        {k: v for k, v in stats.items() if domain != "sandhi" or is_sandhi_chapter(k)}
    )
    print("-" * len(header))
    overall_pct = 100.0 * active / total if total else 0.0
    sandhi_total = sum(v["total"] for ch, v in stats.items() if is_sandhi_chapter(ch))
    sandhi_active = sum(v["active"] for ch, v in stats.items() if is_sandhi_chapter(ch))
    sandhi_pct = 100.0 * sandhi_active / sandhi_total if sandhi_total else 0.0

    print(f"\n  TOTAL     {total:>6} {active:>8} {passive:>8} {overall_pct:>9.1f}%")
    print(f"  SANDHI    {sandhi_total:>6} {sandhi_active:>8} {'':>8} {sandhi_pct:>9.1f}%")
    print(f"\n  Sandhi target: ≥ 95.0% coverage  (currently {sandhi_pct:.1f}%)")
    if sandhi_pct >= 95.0:
        print("  🎉 Sandhi coverage target MET — no structural hardcoding required.")
    else:
        gap = sandhi_total - sandhi_active
        print(f"  ⚠️  {gap} sandhi-domain rules still produce non_operational/governance output.")
        print("     These represent rules the engine cannot yet interpret generically.")
    print()

    # Print op-type breakdown for sandhi chapters
    print("\n  Op-type breakdown for sandhi chapters (6.1, 8.x):")
    op_totals: Dict[str, int] = {}
    for ch, v in stats.items():
        if not is_sandhi_chapter(ch):
            continue
        for op, cnt in v["op_counts"].items():
            op_totals[op] = op_totals.get(op, 0) + cnt
    for op, cnt in sorted(op_totals.items(), key=lambda x: -x[1]):
        flag = "✅" if op in ACTIVE_OPS else "❌"
        print(f"    {flag} {op:<35} {cnt:>5}")


def main():
    parser = argparse.ArgumentParser(description="Sanskrit engine rule coverage validator")
    parser.add_argument("--domain", choices=["all", "sandhi"], default="sandhi",
                        help="Which chapters to report (default: sandhi)")
    parser.add_argument("--chapter", type=str, default=None,
                        help="Show stats for a single chapter only (e.g. '8.2')")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"Error: DB not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    stats = load_coverage(conn, chapter_filter=args.chapter)
    conn.close()

    report(stats, domain=args.domain if not args.chapter else "all")


if __name__ == "__main__":
    main()
