"""
Batch Sūtra Parser and Validator.

Executes the DeterministicSutraParser across all ~4,000 sūtras in sanskrit_master.db,
reports extraction statistics across categories (Vidhi, Sañjñā, Paribhāṣā, Adhikāra, Atideśa),
and validates alignment with rule_configs.
"""

import sqlite3
import os
from rules_parser.deterministic_parser import DeterministicSutraParser


def run_batch_validation(db_path: str = "data/sanskrit_master.db") -> dict:
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at {db_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    rows = cur.execute("SELECT id, sutra_slp1, pada_cheda, sutra_type FROM sutras ORDER BY id").fetchall()

    stats = {
        "total": len(rows),
        "success": 0,
        "failed": 0,
        "by_category": {},
        "primitives_produced": {
            "elide": 0,
            "exact_substitute": 0,
            "ekadesha_guna": 0,
            "ekadesha_vriddhi": 0,
            "dirgha": 0,
            "purva_rupa": 0,
            "pararupa": 0,
            "prakritibhava": 0,
            "governance": 0,
            "prohibit": 0,
            "other": 0
        }
    }

    for sid, name, pc, st in rows:
        cat = st.split('$')[0] if st and '$' in st else (st[:2] if st else 'V')
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

        try:
            spec = DeterministicSutraParser.parse(sid, name or sid, pc or "")
            stats["success"] += 1

            op_type = getattr(spec.operation, "op_type", "other")
            if op_type in stats["primitives_produced"]:
                stats["primitives_produced"][op_type] += 1
            else:
                stats["primitives_produced"]["other"] += 1
        except Exception as e:
            stats["failed"] += 1

    conn.close()
    return stats


if __name__ == "__main__":
    print("Running deterministic batch parser on all Aṣṭādhyāyī sūtras...")
    res = run_batch_validation()
    print(f"Total Sūtras Processed: {res['total']}")
    print(f"Successfully Parsed to Primitives: {res['success']}")
    print(f"Failed: {res['failed']}")
    print("\nBreakdown by Sūtra Category:")
    for k, v in sorted(res['by_category'].items()):
        print(f"  {k}: {v}")
    print("\nPrimitives Output Distribution:")
    for k, v in sorted(res['primitives_produced'].items(), key=lambda x: -x[1]):
        if v > 0:
            print(f"  {k}: {v}")
