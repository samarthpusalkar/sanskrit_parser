"""
Verify local `sutras` table against upstream ashtadhyayi-data repository.

The upstream sūtra source of truth is:
    data/ashtadhyayi-data/sutraani/data.txt

This script compares the local DB's `sutras` table against that upstream JSON
file and reports mismatches. It can also optionally print a fix-diff.

Usage:
    python3 tools/verify_ashtadhyayi_data.py --check
    python3 tools/verify_ashtadhyayi_data.py --fix
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from typing import Dict, List, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sanskrit_master.db")
UPSTREAM_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "ashtadhyayi-data", "sutraani", "data.txt"
)


def _normalize_id(numeric_id: str) -> str:
    """Convert upstream numeric id like 11001 to canonical 1.1.1."""
    if len(numeric_id) >= 5:
        adhyaya = numeric_id[0]
        pada = numeric_id[1]
        sutra_no = str(int(numeric_id[2:]))
        return f"{adhyaya}.{pada}.{sutra_no}"
    return numeric_id


def _normalize_text(value: str) -> str:
    """Normalize whitespace so trivial differences don't flag mismatches."""
    if not value:
        return ""
    return " ".join(value.split())


def _load_upstream(path: str) -> Dict[str, Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: Dict[str, Dict[str, str]] = {}
    for row in data.get("data", []):
        sid = _normalize_id(row["i"])
        out[sid] = {
            "sutra_dev": _normalize_text(row.get("s", "") or ""),
            "sutra_slp1": _normalize_text(row.get("e", "") or ""),
            "sutra_type": _normalize_text(row.get("type", "") or ""),
            "pada_cheda": _normalize_text(row.get("pc", "") or ""),
            "samasta_sutra": _normalize_text(row.get("ss", "") or ""),
            "anuvrtti": _normalize_text(row.get("an", "") or ""),
            "adhikara": _normalize_text(row.get("ad", "") or ""),
        }
    return out


def _load_local(db_path: str) -> Dict[str, Tuple[str, ...]]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, sutra_dev, sutra_slp1, sutra_type, pada_cheda, "
        "samasta_sutra, anuvrtti, adhikara FROM sutras"
    ).fetchall()
    conn.close()
    return {r[0]: tuple(_normalize_text(v) for v in r[1:]) for r in rows}


def _row_hash(row: Tuple[str, ...]) -> str:
    return hashlib.sha256(
        json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


def check(db_path: str = DB_PATH, upstream_path: str = UPSTREAM_PATH, include_slp1: bool = False) -> dict:
    upstream = _load_upstream(upstream_path)
    local = _load_local(db_path)

    only_upstream = []
    only_local = []
    mismatched = []
    matched = 0

    # Fields that matter for extraction correctness. sutra_slp1 is excluded by
    # default because upstream and local use different transliteration conventions.
    compare_keys = ["sutra_dev", "sutra_type", "pada_cheda", "samasta_sutra", "anuvrtti", "adhikara"]
    if include_slp1:
        compare_keys.append("sutra_slp1")

    for sid, u_row in upstream.items():
        if sid not in local:
            only_upstream.append(sid)
            continue
        local_vals = {
            "sutra_dev": local[sid][0],
            "sutra_slp1": local[sid][1],
            "sutra_type": local[sid][2],
            "pada_cheda": local[sid][3],
            "samasta_sutra": local[sid][4],
            "anuvrtti": local[sid][5],
            "adhikara": local[sid][6],
        }
        diff = {k: {"upstream": u_row[k], "local": local_vals[k]} for k in compare_keys if u_row[k] != local_vals[k]}
        if diff:
            mismatched.append({
                "sutra_id": sid,
                "diff": diff,
            })
        else:
            matched += 1

    for sid in local:
        if sid not in upstream:
            only_local.append(sid)

    return {
        "upstream_count": len(upstream),
        "local_count": len(local),
        "matched": matched,
        "only_upstream": only_upstream,
        "only_local": only_local,
        "mismatched": mismatched,
    }


def fix(db_path: str = DB_PATH, upstream_path: str = UPSTREAM_PATH) -> int:
    upstream = _load_upstream(upstream_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    updated = 0
    for sid, u in upstream.items():
        cursor.execute(
            """INSERT OR REPLACE INTO sutras
               (id, sutra_dev, sutra_slp1, sutra_type, pada_cheda,
                samasta_sutra, anuvrtti, adhikara)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (sid, u["sutra_dev"], u["sutra_slp1"], u["sutra_type"],
             u["pada_cheda"], u["samasta_sutra"], u["anuvrtti"], u["adhikara"]),
        )
        updated += 1
    conn.commit()
    conn.close()
    return updated


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify local sutras table against upstream ashtadhyayi-data"
    )
    parser.add_argument("--check", action="store_true",
                        help="Compare local DB against upstream and report mismatches")
    parser.add_argument("--fix", action="store_true",
                        help="Overwrite local sutras table with upstream data")
    parser.add_argument("--include-slp1", action="store_true",
                        help="Also compare sutra_slp1 column (excluded by default)")
    parser.add_argument("--db-path", default=DB_PATH)
    parser.add_argument("--upstream-path", default=UPSTREAM_PATH)
    args = parser.parse_args(argv)

    if args.fix:
        updated = fix(args.db_path, args.upstream_path)
        print(f"Fixed {updated} rows from {args.upstream_path}")
        return 0

    if args.check:
        result = check(args.db_path, args.upstream_path, include_slp1=args.include_slp1)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result["only_upstream"] or result["only_local"] or result["mismatched"]:
            return 1
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
